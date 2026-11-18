import json
import math
import subprocess
from pathlib import Path
from typing import Any

import whisper
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from loguru import logger

_MODEL_CACHE: dict[str, Any] = {}


def clear_model_cache() -> None:
    """Forget every loaded Whisper model (used by tests and on settings changes)."""
    _MODEL_CACHE.clear()


def get_model(name: str) -> Any:
    """Return the Whisper model ``name``, loading it only once per worker process.

    Args:
        name: Whisper model size (tiny, base, small, medium, large).

    Returns:
        The loaded model.
    """
    if name not in _MODEL_CACHE:
        _MODEL_CACHE[name] = whisper.load_model(name)
    return _MODEL_CACHE[name]


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


class VideoProcessor:
    """
    Handles the full pipeline for processing a video transcription job:
    - Extracts audio from the video file
    - Transcribes the audio using OpenAI Whisper
    - Generates subtitle files (SRT, VTT, JSON, TXT)
    - Muxes the subtitles into the video (soft subtitles)
    - Updates job progress and logs each step

    Args:
        job (TranscriptionJob): Django model instance representing the transcription job.

    Example:
        processor = VideoProcessor(job)
        processor.process()
    """

    def __init__(self, job):
        """
        Initialize the processor with a transcription job.

        Args:
            job (TranscriptionJob): Django model instance for the job.
        """
        self.job = job

    def update_progress(self, percentage: int, step: str) -> None:
        """
        Update the job's progress and current step, then save and log it.

        Args:
            percentage (int): Progress percentage (0-100).
            step (str): Description of the current step.

        Returns:
            None

        Example:
            self.update_progress(40, "Transcribing audio")
        """
        self.job.progress_percentage = percentage
        self.job.current_step = step
        self.job.save()
        logger.info(f"[{self.job.id}] Progress: {percentage}% - {step}")

    def extract_audio(self) -> bool:
        """
        Extracts audio from the job's video file and saves it as a mono 16kHz WAV file.

        Returns:
            bool: True if successful, False otherwise.

        Example:
            processor.extract_audio()
        """
        self.update_progress(20, "Extracting audio...")
        video_path = self.job.video_file.path
        audio_path = f"{video_path}_temp.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            audio_path,
        ]
        logger.info(f"[{self.job.id}] Running command: {' '.join(cmd)}")
        try:
            # Fixed ffmpeg argv, no shell; paths come from our own storage.
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
            with open(audio_path, "rb") as audio_file:
                self.job.audio_file.save(f"{self.job.id}_audio.wav", File(audio_file))
            Path(audio_path).unlink()
            logger.success(f"[{self.job.id}] Audio extracted successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[{self.job.id}] Audio extraction error: {e}")
            return False

    def transcribe_audio(self):
        """
        Transcribes the extracted audio using the Whisper model and saves segments to the database.

        Returns:
            dict or None: Whisper result dictionary if successful, None otherwise.

        Example:
            processor.transcribe_audio()
        """
        self.update_progress(60, "Transcribing with Whisper...")
        try:
            logger.info(f"[{self.job.id}] Loading Whisper model...")
            model = get_model(settings.WHISPER_DEFAULT_MODEL)
            logger.info(f"[{self.job.id}] Transcribing audio '{self.job.audio_file.path}'")
            result = model.transcribe(self.job.audio_file.path, language="pt")
            from .models import SubtitleSegment

            for segment in result["segments"]:
                SubtitleSegment.objects.create(
                    job=self.job,
                    start_time=segment["start"],
                    end_time=segment["end"],
                    text=segment["text"],
                    confidence=confidence_from_logprob(segment.get("avg_logprob")),
                )
            logger.success(f"[{self.job.id}] Transcription completed.")
            return result
        except Exception as e:
            logger.error(f"[{self.job.id}] Transcription error: {e}")
            return None

    def generate_subtitle_files(self) -> None:
        """
        Generates SRT, VTT, JSON, and TXT files from the subtitle segments.

        Returns:
            None

        Example:
            processor.generate_subtitle_files()
        """
        self.update_progress(80, "Generating subtitle files...")
        logger.info(f"[{self.job.id}] Generating subtitle files...")

        # Only use segments with non-empty, non-whitespace text
        segments = [seg for seg in self.job.segments.all() if seg.text and seg.text.strip()]
        logger.info(
            f"[{self.job.id}] {len(segments)} non-silent segments will be used for subtitles."
        )

        # SRT
        srt_content = self._generate_srt(segments)
        srt_file = ContentFile(srt_content.encode("utf-8"))
        self.job.srt_file.save(f"{self.job.id}.srt", srt_file)
        logger.success(f"[{self.job.id}] SRT file generated.")

        # VTT
        vtt_content = self._generate_vtt(segments)
        vtt_file = ContentFile(vtt_content.encode("utf-8"))
        self.job.vtt_file.save(f"{self.job.id}.vtt", vtt_file)
        logger.success(f"[{self.job.id}] VTT file generated.")

        # JSON
        json_data = [
            {
                "start": seg.start_time,
                "end": seg.end_time,
                "text": seg.text,
                "confidence": seg.confidence,
            }
            for seg in segments
        ]
        json_content = json.dumps(json_data, indent=2, ensure_ascii=False)
        json_file = ContentFile(json_content.encode("utf-8"))
        self.job.json_file.save(f"{self.job.id}.json", json_file)
        logger.success(f"[{self.job.id}] JSON file generated.")

        # TXT
        txt_content = "\n".join([seg.text for seg in segments])
        txt_file = ContentFile(txt_content.encode("utf-8"))
        self.job.transcript_file.save(f"{self.job.id}_transcript.txt", txt_file)
        logger.success(f"[{self.job.id}] TXT transcript generated.")

    def _generate_srt(self, segments) -> str:
        """
        Generates SRT file content from subtitle segments.

        Args:
            segments (QuerySet): Subtitle segments.

        Returns:
            str: SRT file content.

        Example:
            srt = processor._generate_srt(segments)
        """
        srt_lines = []
        idx = 1
        for seg in segments:
            if not seg.text or not seg.text.strip():
                continue  # Skip silent segments
            start = self._format_srt_timestamp(seg.start_time)
            end = self._format_srt_timestamp(seg.end_time)
            srt_lines.append(f"{idx}\n{start} --> {end}\n{seg.text.strip()}\n")
            idx += 1
        return "\n".join(srt_lines)

    def _generate_vtt(self, segments) -> str:
        """
        Generates VTT file content from subtitle segments.

        Args:
            segments (QuerySet): Subtitle segments.

        Returns:
            str: VTT file content.

        Example:
            vtt = processor._generate_vtt(segments)
        """
        vtt_lines = ["WEBVTT\n"]
        for seg in segments:
            if not seg.text or not seg.text.strip():
                continue  # Skip silent segments
            start = self._format_vtt_timestamp(seg.start_time)
            end = self._format_vtt_timestamp(seg.end_time)
            vtt_lines.append(f"{start} --> {end}\n{seg.text.strip()}\n")
        return "\n".join(vtt_lines)

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Converts seconds to SRT timestamp format (HH:MM:SS,mmm).

        Args:
            seconds (float): Time in seconds.

        Returns:
            str: SRT timestamp.

        Example:
            processor._format_srt_timestamp(65.123)  # "00:01:05,123"
        """
        total_ms = round(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _format_vtt_timestamp(self, seconds: float) -> str:
        """
        Converts seconds to VTT timestamp format (HH:MM:SS.mmm).

        Args:
            seconds (float): Time in seconds.

        Returns:
            str: VTT timestamp.

        Example:
            processor._format_vtt_timestamp(65.123)  # "00:01:05.123"
        """
        total_ms = round(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

    def mux_soft_subtitle(self) -> bool:
        """
        Adds the SRT subtitle file to the video as a soft subtitle track (mov_text).

        Returns:
            bool: True if successful, False otherwise.

        Example:
            processor.mux_soft_subtitle()
        """
        self.update_progress(90, "Muxing final video...")
        video_path = self.job.video_file.path
        srt_path = self.job.srt_file.path
        output_path = f"{video_path}_with_subtitles.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            srt_path,
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=por",
            output_path,
        ]
        logger.info(f"[{self.job.id}] Running command: {' '.join(cmd)}")
        try:
            # Fixed ffmpeg argv, no shell; paths come from our own storage.
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
            with open(output_path, "rb") as video_file:
                self.job.final_video.save(f"{self.job.id}_with_subtitles.mp4", File(video_file))
            Path(output_path).unlink()
            logger.success(f"[{self.job.id}] Final video with soft subtitles muxed.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[{self.job.id}] Muxing error: {e}")
            return False

    def process(self) -> None:
        """
        Runs the full processing pipeline:
        - Audio extraction
        - Audio transcription
        - Subtitle file generation
        - Video muxing

        Returns:
            None

        Example:
            processor = VideoProcessor(job)
            processor.process()
        """
        try:
            self.job.status = "extracting"
            self.job.save()
            logger.info(f"[{self.job.id}] Starting audio extraction...")
            if not self.extract_audio():
                raise Exception("Audio extraction failed")
            self.job.status = "transcribing"
            self.job.save()
            logger.info(f"[{self.job.id}] Starting audio transcription...")
            if not self.transcribe_audio():
                raise Exception("Transcription failed")
            self.job.status = "generating"
            self.job.save()
            logger.info(f"[{self.job.id}] Generating subtitle files...")
            self.generate_subtitle_files()
            logger.info(f"[{self.job.id}] Muxing final video...")
            if not self.mux_soft_subtitle():
                raise Exception("Subtitle embedding failed")
            self.job.status = "completed"
            self.job.progress_percentage = 100
            self.job.current_step = "Processing completed!"
            self.job.save()
            logger.success(f"[{self.job.id}] Pipeline completed successfully.")
        except Exception as e:
            self.job.status = "failed"
            self.job.current_step = f"Error: {str(e)}"
            self.job.save()
            logger.error(f"[{self.job.id}] Processing error: {e}")


# ------------------------------
# Example usage:
#
# processor = VideoProcessor(job)
# processor.process()
