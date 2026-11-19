"""Pipeline behaviour driven by per-job options, cancellation and media kind."""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from django.core.files.base import ContentFile
from pytest_django.fixtures import Settings

from core import tasks, utils
from core.models import JobStatus, TranscriptionJob
from core.utils import VideoProcessor

pytestmark = pytest.mark.django_db

RESULT = {"segments": [{"start": 0.0, "end": 1.0, "text": " Oi", "avg_logprob": -0.1}]}


@pytest.fixture(autouse=True)
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def ffmpeg(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Fake ffmpeg that writes its output file (last argv item)."""

    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        Path(cmd[-1]).write_bytes(b"fake-output")
        return subprocess.CompletedProcess(cmd, 0)

    runner = MagicMock(side_effect=run)
    monkeypatch.setattr(utils.subprocess, "run", runner)
    return runner


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Fake Whisper model; the loader is available as ``model.loader``."""
    fake = MagicMock()
    fake.transcribe.return_value = RESULT
    loader = MagicMock(return_value=fake)
    monkeypatch.setattr(utils.whisper, "load_model", loader)
    monkeypatch.setattr(utils, "is_model_downloaded", lambda name: True)
    monkeypatch.setattr(utils, "cuda_available", lambda: False)
    fake.loader = loader
    return fake


def make_job(name: str = "clip.mp4", **fields: Any) -> TranscriptionJob:
    """A queued job with a fake media file."""
    job = TranscriptionJob(status=JobStatus.QUEUED, original_filename=name, **fields)
    job.media_file.save(name, ContentFile(b"media"), save=False)
    job.save()
    return job


def test_uses_the_job_language_model_and_device(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job(language="en", model_name="tiny", device="cpu")

    VideoProcessor(job).process()

    model.loader.assert_called_once_with("tiny", device="cpu")
    assert model.transcribe.call_args.kwargs["language"] == "en"
    job.refresh_from_db()
    assert job.status == JobStatus.COMPLETED
    assert job.current_step == "Concluído"


def test_auto_language_lets_whisper_detect(ffmpeg: MagicMock, model: MagicMock) -> None:
    VideoProcessor(make_job(language="auto")).process()
    assert model.transcribe.call_args.kwargs["language"] is None


def test_auto_device_lets_whisper_choose(ffmpeg: MagicMock, model: MagicMock) -> None:
    VideoProcessor(make_job(device="auto")).process()
    model.loader.assert_called_once_with("small", device=None)


def test_gpu_job_fails_clearly_without_cuda(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job(device="gpu")

    VideoProcessor(job).process()

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "GPU" in job.error_message
    model.loader.assert_not_called()


def test_gpu_job_uses_cuda(
    ffmpeg: MagicMock, model: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(utils, "cuda_available", lambda: True)
    VideoProcessor(make_job(device="gpu")).process()
    model.loader.assert_called_once_with("small", device="cuda")


def test_audio_media_skips_the_subtitled_video(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job("podcast.mp3", media_kind="audio")

    VideoProcessor(job).process()

    job.refresh_from_db()
    assert job.status == JobStatus.COMPLETED
    assert not job.final_video
    assert job.srt_file
    assert ffmpeg.call_count == 1


def test_missing_model_shows_download_status(
    ffmpeg: MagicMock, model: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = make_job()
    seen: list[str] = []
    monkeypatch.setattr(utils, "is_model_downloaded", lambda name: False)
    model.loader.side_effect = lambda *a, **k: (
        seen.append(TranscriptionJob.objects.get(pk=job.pk).status) or model
    )

    VideoProcessor(job).process()

    assert seen == [JobStatus.DOWNLOADING_MODEL]


def test_cancel_during_processing_is_not_overwritten(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job()

    def cancel_then_load(*args: Any, **kwargs: Any) -> MagicMock:
        TranscriptionJob.objects.filter(pk=job.pk).update(status=JobStatus.CANCELLED)
        return model

    model.loader.side_effect = cancel_then_load

    VideoProcessor(job).process()

    job.refresh_from_db()
    assert job.status == JobStatus.CANCELLED
    assert not job.srt_file


def test_failure_message_is_shown_to_the_person(
    model: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = subprocess.CalledProcessError(1, ["ffmpeg"])
    monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=error))
    job = make_job()

    VideoProcessor(job).process()

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert job.error_message == "Não foi possível extrair o áudio do arquivo."


def test_task_skips_a_job_cancelled_before_it_started(monkeypatch: pytest.MonkeyPatch) -> None:
    job = make_job()
    TranscriptionJob.objects.filter(pk=job.pk).update(status=JobStatus.CANCELLED)
    process = MagicMock()
    monkeypatch.setattr(tasks.VideoProcessor, "process", process)

    tasks.process_video_task.apply(args=[str(job.id)])

    process.assert_not_called()


@pytest.mark.parametrize(("code", "expected"), [(0, True), (1, False)])
def test_gpu_probe_reads_the_subprocess_exit_code(
    monkeypatch: pytest.MonkeyPatch, code: int, expected: bool
) -> None:
    runner = MagicMock(return_value=subprocess.CompletedProcess([], code))
    monkeypatch.setattr(utils.subprocess, "run", runner)
    assert utils.detect_gpu_in_subprocess() is expected


def test_gpu_probe_timeout_means_no_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    error = subprocess.TimeoutExpired(["python"], 1)
    monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=error))
    assert utils.detect_gpu_in_subprocess() is False


def test_gpu_out_of_memory_explains_and_frees_the_model(
    ffmpeg: MagicMock, model: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(utils, "cuda_available", lambda: True)
    freed = MagicMock()
    monkeypatch.setattr(utils, "free_gpu_memory", freed)
    model.transcribe.side_effect = RuntimeError("CUDA out of memory. Tried to allocate 20 MiB")
    job = make_job(device="gpu", model_name="medium")

    VideoProcessor(job).process()

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert job.error_message == (
        "Memória de vídeo insuficiente para o modelo medium. "
        "Escolha um modelo menor ou processe com CPU."
    )
    assert ("medium", "cuda") not in utils._MODEL_CACHE
    freed.assert_called_once()


def test_media_without_speech_completes_without_subtitled_video(
    ffmpeg: MagicMock, model: MagicMock
) -> None:
    model.transcribe.return_value = {"segments": []}
    job = make_job()

    VideoProcessor(job).process()

    job.refresh_from_db()
    assert job.status == JobStatus.COMPLETED
    assert job.current_step == "Concluído: nenhuma fala encontrada"
    assert not job.final_video
    assert ffmpeg.call_count == 1


ANALYSIS_TWO_SUBS = {
    "subtitles": [{"language": "por", "title": "A"}, {"language": "eng", "title": "B"}]
}


def argv_of(ffmpeg: MagicMock, call: int) -> list[str]:
    """The argv of the n-th ffmpeg call."""
    return ffmpeg.call_args_list[call].args[0]


def test_preview_copies_picture_and_converts_the_chosen_track(
    ffmpeg: MagicMock, model: MagicMock
) -> None:
    job = make_job("ep.mkv", make_preview=True, audio_stream_index=2, analysis=ANALYSIS_TWO_SUBS)
    seen: list[str] = []
    model.loader.side_effect = lambda *a, **k: (
        seen.append(TranscriptionJob.objects.get(pk=job.pk).preview_file.name) or model
    )

    VideoProcessor(job).process()

    preview = argv_of(ffmpeg, 0)
    assert preview[preview.index("-map") + 1] == "0:v:0"
    assert "0:2" in preview
    assert preview[preview.index("-c:v") + 1] == "copy"
    assert preview[preview.index("-c:a") + 1] == "aac"
    assert preview[preview.index("-ac") + 1] == "2"
    assert preview[-1].endswith(".mp4")
    assert seen and seen[0].startswith("previews/")
    job.refresh_from_db()
    assert job.status == JobStatus.COMPLETED


def test_preview_can_reencode_the_picture(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job("ep.mkv", make_preview=True, convert_video=True, audio_stream_index=1)
    VideoProcessor(job).process()
    preview = argv_of(ffmpeg, 0)
    assert preview[preview.index("-c:v") + 1] == "libx264"


def test_audio_only_preview_is_m4a(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job("ep.ogg", media_kind="audio", make_preview=True, audio_stream_index=0)
    VideoProcessor(job).process()
    preview = argv_of(ffmpeg, 0)
    assert "-vn" in preview and preview[-1].endswith(".m4a")


def test_no_preview_when_not_asked(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job("ep.mp4", make_preview=False)
    VideoProcessor(job).process()
    assert not any(
        argv[-1].endswith("_preview.mp4") for argv in (c.args[0] for c in ffmpeg.call_args_list)
    )


def test_extraction_uses_the_chosen_track(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job("ep.mkv", audio_stream_index=2)
    VideoProcessor(job).process()
    extract = argv_of(ffmpeg, 0)
    assert extract[extract.index("-map") + 1] == "0:2"


def test_mkv_keeps_every_original_track_and_adds_ours_as_default(
    ffmpeg: MagicMock, model: MagicMock
) -> None:
    job = make_job("ep.mkv", language="en", audio_stream_index=1, analysis=ANALYSIS_TWO_SUBS)

    VideoProcessor(job).process()

    mux = argv_of(ffmpeg, -1)
    assert mux[-1].endswith("_with_subtitles.mkv")
    assert ["-map", "0", "-map", "1"] == mux[mux.index("-map") : mux.index("-map") + 4]
    assert mux[mux.index("-c") + 1] == "copy"
    assert "-c:s" not in mux
    assert mux[mux.index("-disposition:s:2") + 1] == "default"
    assert "language=eng" in mux
    job.refresh_from_db()
    assert job.final_video.name.endswith(".mkv")


def test_mp4_converts_subtitles_to_mov_text(ffmpeg: MagicMock, model: MagicMock) -> None:
    job = make_job("aula.mp4", language="pt")
    VideoProcessor(job).process()
    mux = argv_of(ffmpeg, -1)
    assert mux[-1].endswith("_with_subtitles.mp4")
    assert mux[mux.index("-c:s") + 1] == "mov_text"
    assert "0:s?" in mux
    assert mux[mux.index("-disposition:s:0") + 1] == "default"
    assert "language=por" in mux
