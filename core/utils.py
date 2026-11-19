"""Transcription pipeline: extract audio → Whisper → subtitle files → subtitled video.

Every status write is conditional on the job still being active, so a job the
person cancelled mid-run is never overwritten by the worker.
"""

import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path, PurePath
from typing import Any

import whisper
from django.core.files import File
from django.core.files.base import ContentFile
from loguru import logger

from .constants import AUTO_LANGUAGE, DEVICE_CPU, DEVICE_GPU
from .models import ACTIVE_STATUSES, JobStatus, MediaKind, SubtitleSegment, TranscriptionJob

PROGRESS_PREVIEW = 3
PROGRESS_DOWNLOAD = 5
PROGRESS_EXTRACT = 20
PROGRESS_TRANSCRIBE = 40
PROGRESS_GENERATE = 80
PROGRESS_MUX = 90
PROGRESS_DONE = 100

WAV_SAMPLE_RATE = 16000
PREVIEW_AUDIO_BITRATE = "160k"
PREVIEW_VIDEO_CRF = "23"
#: App language code → ISO 639-2 tag written on our subtitle track.
SUBTITLE_LANGUAGE_TAGS = {"pt": "por", "en": "eng", "es": "spa"}
SUBTITLE_TRACK_TITLE = "Video Transcription"

_MODEL_CACHE: dict[tuple[str, str | None], Any] = {}


class PipelineError(Exception):
    """A step failed. The message is pt-BR and shown to the person."""


class JobCancelledError(Exception):
    """The job left the active statuses (cancelled) while it was being processed."""


def clear_model_cache() -> None:
    """Forget every loaded Whisper model (used by tests and on settings changes)."""
    _MODEL_CACHE.clear()


def get_model(name: str, device: str | None = None) -> Any:
    """Return the Whisper model, loading it only once per worker process and device.

    Args:
        name: Whisper model size (tiny, base, small, medium, large).
        device: ``"cpu"``, ``"cuda"`` or None to let Whisper choose.

    Returns:
        The loaded model.
    """
    key = (name, device)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = whisper.load_model(name, device=device)
    return _MODEL_CACHE[key]


def free_gpu_memory() -> None:
    """Release cached CUDA memory held by PyTorch in this process."""
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def is_model_downloaded(name: str) -> bool:
    """Whether the Whisper checkpoint for ``name`` is already in the local cache.

    Args:
        name: Whisper model size.

    Returns:
        True when the file exists, so loading will not download it.
    """
    url = whisper._MODELS.get(name)  # noqa: SLF001 - no public API exposes the file name
    if url is None:
        return False
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "whisper"
    return (cache_dir / os.path.basename(url)).exists()


def cuda_available() -> bool:
    """Whether PyTorch can use an NVIDIA GPU in this process."""
    import torch

    return bool(torch.cuda.is_available())


GPU_PROBE_TIMEOUT_SECONDS = 120
_GPU_PROBE = "import sys, torch; sys.exit(0 if torch.cuda.is_available() else 1)"


def detect_gpu_in_subprocess() -> bool:
    """Check for a usable NVIDIA GPU without initialising CUDA in this process.

    The Celery prefork pool forks job processes from the worker's main process;
    once CUDA is initialised there, forked children can no longer use it. So the
    worker asks a short-lived Python process instead.

    Returns:
        True when PyTorch in a fresh process can use CUDA.
    """
    try:
        # Fixed argv (our own interpreter and a constant snippet), no shell.
        probe = subprocess.run(  # noqa: S603
            [sys.executable, "-c", _GPU_PROBE],
            capture_output=True,
            timeout=GPU_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("GPU probe timed out; assuming no GPU.")
        return False
    return probe.returncode == 0


def confidence_from_logprob(avg_logprob: float | None) -> float | None:
    """Turn Whisper's average token log-probability into a 0..1 confidence.

    Args:
        avg_logprob: ``avg_logprob`` of a Whisper segment, if present.

    Returns:
        ``exp(avg_logprob)`` clamped to [0, 1], or None when unavailable.
    """
    if avg_logprob is None:
        return None
    return min(1.0, max(0.0, math.exp(avg_logprob)))


def wav_duration_seconds(path: str) -> float | None:
    """Duration of a WAV file, or None if it cannot be read.

    Args:
        path: WAV file path.

    Returns:
        Seconds, or None (logged) when the header is unreadable.
    """
    try:
        with wave.open(path, "rb") as audio:
            return audio.getnframes() / float(audio.getframerate())
    except (wave.Error, EOFError) as error:
        logger.warning(f"Could not read WAV duration from {path}: {error}")
        return None


class VideoProcessor:
    """Runs the full pipeline for one job, using the job's language, model and device."""

    def __init__(self, job: TranscriptionJob) -> None:
        """Bind the processor to a job.

        Args:
            job: The job to process.
        """
        self.job = job

    # ----- state ---------------------------------------------------------

    def _write(self, **fields: Any) -> None:
        """Persist ``fields`` only while the job is still active.

        Args:
            **fields: Model fields to update.

        Raises:
            JobCancelledError: If the job is no longer active (cancelled).
        """
        updated = TranscriptionJob.objects.filter(
            pk=self.job.pk, status__in=ACTIVE_STATUSES
        ).update(**fields)
        if not updated:
            raise JobCancelledError
        for name, value in fields.items():
            setattr(self.job, name, value)

    def _step(self, status: str, percentage: int, label: str) -> None:
        """Move to a new step.

        Args:
            status: New JobStatus.
            percentage: Progress 0..100.
            label: pt-BR step text shown on the page.
        """
        self._write(status=status, progress_percentage=percentage, current_step=label)
        logger.info(f"[{self.job.id}] {percentage}% - {label}")

    def _store(self, field: str, name: str, content: File) -> None:
        """Save a generated file and record it on the job.

        Args:
            field: FileField name.
            name: File name inside the field's folder.
            content: File content.
        """
        stored = getattr(self.job, field)
        stored.save(name, content, save=False)
        self._write(**{field: stored.name})

    def _ffmpeg(self, cmd: list[str], message: str) -> None:
        """Run ffmpeg, turning a failure into a PipelineError.

        Args:
            cmd: Full ffmpeg argv (fixed program, paths from our own storage).
            message: pt-BR error shown to the person on failure.

        Raises:
            PipelineError: If ffmpeg exits with an error.
        """
        try:
            # Fixed ffmpeg argv, no shell; paths come from our own storage.
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
        except subprocess.CalledProcessError as error:
            logger.error(f"[{self.job.id}] ffmpeg failed: {error.stderr!r}")
            raise PipelineError(message) from error

    def _audio_map(self) -> list[str]:
        """``-map`` arguments selecting the chosen audio track (default: ffmpeg's pick)."""
        index = self.job.audio_stream_index
        return [] if index is None else ["-map", f"0:{index}"]

    # ----- steps ---------------------------------------------------------

    def prepare_preview(self) -> None:
        """Build the browser Prévia: picture copied (or re-encoded) + chosen track as AAC stereo.

        Raises:
            PipelineError: If ffmpeg fails.
        """
        self._step(JobStatus.PREPARING_PREVIEW, PROGRESS_PREVIEW, "Preparando prévia…")
        media_path = self.job.media_file.path
        is_video = self.job.media_kind == MediaKind.VIDEO
        output_path = f"{media_path}_preview.{'mp4' if is_video else 'm4a'}"
        if is_video:
            picture = (
                ["-c:v", "libx264", "-preset", "veryfast", "-crf", PREVIEW_VIDEO_CRF,
                 "-pix_fmt", "yuv420p"]
                if self.job.convert_video
                else ["-c:v", "copy"]
            )  # fmt: skip
            video_args = ["-map", "0:v:0", *picture]
        else:
            video_args = ["-vn"]
        audio_map = self._audio_map() or ["-map", "0:a:0"]
        cmd = [
            "ffmpeg", "-y", "-i", media_path, *video_args, *audio_map,
            "-c:a", "aac", "-ac", "2", "-b:a", PREVIEW_AUDIO_BITRATE,
            "-sn", "-movflags", "+faststart", output_path,
        ]  # fmt: skip
        self._ffmpeg(cmd, "Não foi possível preparar a prévia para o navegador.")
        with open(output_path, "rb") as preview:
            self._store("preview_file", PurePath(output_path).name, File(preview))
        Path(output_path).unlink()

    def _resolve_device(self) -> str | None:
        """Translate the job's device choice into a Whisper device.

        Raises:
            PipelineError: If the GPU was chosen but is not available.
        """
        if self.job.device == DEVICE_CPU:
            return "cpu"
        if self.job.device == DEVICE_GPU:
            if not cuda_available():
                raise PipelineError("GPU indisponível neste computador.")
            return "cuda"
        return None

    def extract_audio(self) -> None:
        """Extract a mono 16 kHz WAV from the media file.

        Raises:
            PipelineError: If ffmpeg fails.
        """
        self._step(JobStatus.EXTRACTING, PROGRESS_EXTRACT, "Extraindo áudio…")
        media_path = self.job.media_file.path
        audio_path = f"{media_path}_temp.wav"
        cmd = [
            "ffmpeg", "-y", "-i", media_path, *self._audio_map(),
            "-vn", "-acodec", "pcm_s16le", "-ar", str(WAV_SAMPLE_RATE), "-ac", "1",
            audio_path,
        ]  # fmt: skip
        self._ffmpeg(cmd, "Não foi possível extrair o áudio do arquivo.")
        with open(audio_path, "rb") as audio:
            self._store("audio_file", f"{self.job.id}_audio.wav", File(audio))
        Path(audio_path).unlink()
        self._write(duration_seconds=wav_duration_seconds(self.job.audio_file.path))

    def transcribe_audio(self, device: str | None) -> None:
        """Transcribe the extracted audio and store the segments.

        Args:
            device: Whisper device from ``_resolve_device``.

        Raises:
            PipelineError: If Whisper fails.
        """
        name = self.job.model_name
        if not is_model_downloaded(name):
            self._step(JobStatus.DOWNLOADING_MODEL, PROGRESS_DOWNLOAD, f"Baixando modelo {name}…")
        try:
            model = get_model(name, device=device)
            self._step(JobStatus.TRANSCRIBING, PROGRESS_TRANSCRIBE, "Transcrevendo com Whisper…")
            language = None if self.job.language == AUTO_LANGUAGE else self.job.language
            result = model.transcribe(self.job.audio_file.path, language=language)
        except JobCancelledError:
            raise
        except Exception as error:
            if "out of memory" in str(error).lower():
                _MODEL_CACHE.pop((name, device), None)
                free_gpu_memory()
                logger.warning(f"[{self.job.id}] GPU out of memory with model {name}.")
                raise PipelineError(
                    f"Memória de vídeo insuficiente para o modelo {name}. "
                    "Escolha um modelo menor ou processe com CPU."
                ) from error
            logger.exception(f"[{self.job.id}] Whisper failed.")
            raise PipelineError("Falha ao transcrever o áudio.") from error
        SubtitleSegment.objects.bulk_create(
            SubtitleSegment(
                job=self.job,
                start_time=segment["start"],
                end_time=segment["end"],
                text=segment["text"],
                confidence=confidence_from_logprob(segment.get("avg_logprob")),
            )
            for segment in result["segments"]
        )

    def generate_subtitle_files(self) -> None:
        """Write SRT, VTT, JSON and TXT from the non-empty segments."""
        self._step(JobStatus.GENERATING, PROGRESS_GENERATE, "Gerando legendas…")
        segments = [seg for seg in self.job.segments.all() if seg.text and seg.text.strip()]
        job_id = self.job.id
        self._store("srt_file", f"{job_id}.srt", _text_file(self._generate_srt(segments)))
        self._store("vtt_file", f"{job_id}.vtt", _text_file(self._generate_vtt(segments)))
        data = [
            {
                "start": seg.start_time,
                "end": seg.end_time,
                "text": seg.text,
                "confidence": seg.confidence,
            }
            for seg in segments
        ]
        json_text = json.dumps(data, indent=2, ensure_ascii=False)
        self._store("json_file", f"{job_id}.json", _text_file(json_text))
        txt = "\n".join(seg.text for seg in segments)
        self._store("transcript_file", f"{job_id}_transcript.txt", _text_file(txt))

    def mux_soft_subtitle(self) -> None:
        """Build the Vídeo legendado: every original track untouched plus our subtitle.

        MKV keeps all streams as they are (our SRT stays SubRip). MP4 can only hold
        text subtitles as mov_text, so subtitles are converted there. Our track is
        the only default subtitle.

        Raises:
            PipelineError: If ffmpeg fails.
        """
        self._step(self.job.status, PROGRESS_MUX, "Embutindo a legenda no vídeo…")
        media_path = self.job.media_file.path
        is_mkv = PurePath(media_path).suffix.lower() == ".mkv"
        extension = "mkv" if is_mkv else "mp4"
        output_path = f"{media_path}_with_subtitles.{extension}"
        ours = len((self.job.analysis or {}).get("subtitles", []))
        tag = SUBTITLE_LANGUAGE_TAGS.get(self.job.language, "und")
        maps = (
            ["-map", "0", "-map", "1", "-c", "copy"]
            if is_mkv
            else ["-map", "0:v", "-map", "0:a", "-map", "0:s?", "-map", "1",
                  "-c", "copy", "-c:s", "mov_text"]
        )  # fmt: skip
        cmd = [
            "ffmpeg", "-y", "-i", media_path, "-i", self.job.srt_file.path, *maps,
            "-disposition:s", "0", f"-disposition:s:{ours}", "default",
            f"-metadata:s:s:{ours}", f"language={tag}",
            f"-metadata:s:s:{ours}", f"title={SUBTITLE_TRACK_TITLE}",
            output_path,
        ]  # fmt: skip
        self._ffmpeg(cmd, "Não foi possível embutir a legenda no vídeo.")
        with open(output_path, "rb") as video:
            self._store("final_video", f"{self.job.id}_with_subtitles.{extension}", File(video))
        Path(output_path).unlink()

    def process(self) -> None:
        """Run every step; record a failure on the job instead of raising."""
        try:
            device = self._resolve_device()
            if self.job.make_preview:
                self.prepare_preview()
            self.extract_audio()
            self.transcribe_audio(device)
            self.generate_subtitle_files()
            has_speech = self.job.segments.exclude(text__regex=r"^\s*$").exists()
            if self.job.media_kind == MediaKind.VIDEO and has_speech:
                self.mux_soft_subtitle()
            label = "Concluído" if has_speech else "Concluído: nenhuma fala encontrada"
            self._step(JobStatus.COMPLETED, PROGRESS_DONE, label)
            logger.success(f"[{self.job.id}] Pipeline completed.")
        except JobCancelledError:
            logger.info(f"[{self.job.id}] Stopped: the job was cancelled.")
        except PipelineError as error:
            self._fail(str(error))

    def _fail(self, message: str) -> None:
        """Mark the job as failed with a message for the person (if still active).

        Args:
            message: pt-BR error text.
        """
        logger.error(f"[{self.job.id}] Failed: {message}")
        try:
            self._write(status=JobStatus.FAILED, error_message=message)
        except JobCancelledError:
            logger.info(f"[{self.job.id}] Not marked failed: it was cancelled meanwhile.")

    # ----- subtitle formats ------------------------------------------------

    def _generate_srt(self, segments: list[SubtitleSegment]) -> str:
        """SRT content from the segments (blank segments skipped).

        Args:
            segments: Segments in time order.

        Returns:
            The SRT text.
        """
        lines = []
        index = 1
        for seg in segments:
            if not seg.text or not seg.text.strip():
                continue
            start = self._format_srt_timestamp(seg.start_time)
            end = self._format_srt_timestamp(seg.end_time)
            lines.append(f"{index}\n{start} --> {end}\n{seg.text.strip()}\n")
            index += 1
        return "\n".join(lines)

    def _generate_vtt(self, segments: list[SubtitleSegment]) -> str:
        """WebVTT content from the segments (blank segments skipped).

        Args:
            segments: Segments in time order.

        Returns:
            The VTT text.
        """
        lines = ["WEBVTT\n"]
        for seg in segments:
            if not seg.text or not seg.text.strip():
                continue
            start = self._format_vtt_timestamp(seg.start_time)
            end = self._format_vtt_timestamp(seg.end_time)
            lines.append(f"{start} --> {end}\n{seg.text.strip()}\n")
        return "\n".join(lines)

    def _format_srt_timestamp(self, seconds: float) -> str:
        """Seconds as ``HH:MM:SS,mmm`` (SRT).

        Args:
            seconds: Time in seconds.

        Returns:
            The timestamp, e.g. ``00:01:05,123`` for 65.123.
        """
        h, m, s, ms = _split_time(seconds)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _format_vtt_timestamp(self, seconds: float) -> str:
        """Seconds as ``HH:MM:SS.mmm`` (WebVTT).

        Args:
            seconds: Time in seconds.

        Returns:
            The timestamp, e.g. ``00:01:05.123`` for 65.123.
        """
        h, m, s, ms = _split_time(seconds)
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def _split_time(seconds: float) -> tuple[int, int, int, int]:
    """Split seconds into hours, minutes, seconds and milliseconds.

    Args:
        seconds: Time in seconds.

    Returns:
        ``(hours, minutes, seconds, milliseconds)``.
    """
    total_ms = round(seconds * 1000)
    return (
        total_ms // 3_600_000,
        (total_ms % 3_600_000) // 60_000,
        (total_ms % 60_000) // 1000,
        total_ms % 1000,
    )


def _text_file(text: str) -> ContentFile:
    """UTF-8 file content from text.

    Args:
        text: File text.

    Returns:
        A ContentFile ready to store.
    """
    return ContentFile(text.encode("utf-8"))
