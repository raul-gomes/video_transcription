"""Regression tests for the bugs listed in docs/pendencias.md (Phase 1)."""

import math
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from django.core.files.base import ContentFile
from pytest_django.fixtures import Settings

from core import utils
from core.models import TranscriptionJob
from core.utils import VideoProcessor
from tests.helpers import FAKE_AUDIO_SECONDS, write_silent_wav
from video_transcription import settings as project_settings
from video_transcription.celery import app as celery_app


@pytest.fixture(autouse=True)
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def job() -> TranscriptionJob:
    """A pending job with a small fake video file."""
    instance = TranscriptionJob(status="queued")
    instance.media_file.save("clip.mp4", ContentFile(b"fake-video"), save=False)
    instance.save()
    return instance


def fake_ffmpeg(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
    """Pretend to run ffmpeg by writing the output file (last argv item)."""
    if cmd[-1].endswith(".wav"):
        write_silent_wav(cmd[-1], FAKE_AUDIO_SECONDS)
    else:
        Path(cmd[-1]).write_bytes(b"fake-output")
    return subprocess.CompletedProcess(cmd, 0)


def whisper_loader(result: dict[str, Any]) -> MagicMock:
    """Build a fake whisper.load_model returning a model that yields ``result``."""
    model = MagicMock()
    model.transcribe.return_value = result
    return MagicMock(return_value=model)


ONE_SEGMENT = {"segments": [{"start": 0.0, "end": 1.0, "text": " Oi", "avg_logprob": -0.25}]}


def test_celery_runs_jobs_asynchronously() -> None:
    """Uploads must not run the whole pipeline inside the request."""
    assert celery_app.conf.task_always_eager is False


def test_worker_takes_one_job_at_a_time() -> None:
    """A worker must not reserve queued jobs while it is busy (ADR 0002)."""
    assert project_settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1


@pytest.mark.django_db
def test_mux_failure_marks_job_failed(
    job: TranscriptionJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed subtitle embed must not report the job as completed."""

    def ffmpeg(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if cmd[-1].endswith("_with_subtitles.mp4"):
            raise subprocess.CalledProcessError(1, cmd)
        return fake_ffmpeg(cmd, **kwargs)

    monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=ffmpeg))
    monkeypatch.setattr(utils.whisper, "load_model", whisper_loader(ONE_SEGMENT))

    VideoProcessor(job).process()
    job.refresh_from_db()

    assert job.status == "failed"
    assert not job.final_video


@pytest.mark.django_db
def test_confidence_comes_from_average_log_probability(
    job: TranscriptionJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whisper has no `confidence` key; derive it from `avg_logprob`."""
    monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=fake_ffmpeg))
    monkeypatch.setattr(utils.whisper, "load_model", whisper_loader(ONE_SEGMENT))

    VideoProcessor(job).process()

    segment = job.segments.get()
    assert segment.confidence == pytest.approx(math.exp(-0.25))


@pytest.mark.django_db
def test_model_is_loaded_once_per_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two jobs in the same worker reuse the loaded Whisper model."""
    loader = whisper_loader(ONE_SEGMENT)
    monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=fake_ffmpeg))
    monkeypatch.setattr(utils.whisper, "load_model", loader)

    for _ in range(2):
        instance = TranscriptionJob(status="queued")
        instance.media_file.save("clip.mp4", ContentFile(b"v"), save=False)
        instance.save()
        VideoProcessor(instance).process()

    assert loader.call_count == 1


@pytest.mark.django_db
def test_unexpected_task_error_marks_job_failed(
    job: TranscriptionJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Errors outside the pipeline must reach the job, not only the result backend."""
    from core import tasks

    monkeypatch.setattr(
        tasks.VideoProcessor, "process", MagicMock(side_effect=RuntimeError("boom"))
    )

    tasks.process_video_task.apply(args=[str(job.id)])
    job.refresh_from_db()

    assert job.status == "failed"
    assert job.error_message == "Erro inesperado: boom"
