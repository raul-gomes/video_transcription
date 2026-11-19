"""Characterization tests for the current transcription pipeline.

ffmpeg and Whisper are replaced by fakes: tests never spawn processes,
download models or touch the network.
"""

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from django.core.files.base import ContentFile
from pytest_django.fixtures import Settings

from core import utils
from core.models import SubtitleSegment, TranscriptionJob
from core.tasks import process_video_task
from core.utils import VideoProcessor
from tests.helpers import FAKE_AUDIO_SECONDS, write_silent_wav

WHISPER_RESULT = {
    "segments": [
        {"start": 0.0, "end": 1.5, "text": " Olá, mundo."},
        {"start": 1.5, "end": 2.0, "text": "   "},
        {"start": 2.0, "end": 65.123, "text": " Segunda frase."},
    ]
}


@pytest.fixture
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def job(media_root: Path) -> TranscriptionJob:
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


@pytest.fixture
def ffmpeg_ok(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace subprocess.run with a successful fake ffmpeg."""
    runner = MagicMock(side_effect=fake_ffmpeg)
    monkeypatch.setattr(utils.subprocess, "run", runner)
    return runner


@pytest.fixture
def whisper_ok(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    """Replace whisper.load_model with a model that returns WHISPER_RESULT."""
    model = MagicMock()
    model.transcribe.return_value = WHISPER_RESULT
    loader = MagicMock(return_value=model)
    monkeypatch.setattr(utils.whisper, "load_model", loader)
    yield loader


class TestTimestamps:
    """SRT uses a comma before milliseconds, VTT uses a dot."""

    @pytest.mark.parametrize(
        ("seconds", "srt", "vtt"),
        [
            (0, "00:00:00,000", "00:00:00.000"),
            (65.123, "00:01:05,123", "00:01:05.123"),
            (3661.9996, "01:01:02,000", "01:01:02.000"),
        ],
    )
    def test_formats(self, seconds: float, srt: str, vtt: str) -> None:
        processor = VideoProcessor(job=MagicMock())
        assert processor._format_srt_timestamp(seconds) == srt
        assert processor._format_vtt_timestamp(seconds) == vtt


@pytest.mark.django_db
class TestPipeline:
    """End-to-end pipeline behaviour with fake ffmpeg and Whisper."""

    def test_happy_path_generates_every_output(
        self, job: TranscriptionJob, ffmpeg_ok: MagicMock, whisper_ok: MagicMock
    ) -> None:
        VideoProcessor(job).process()
        job.refresh_from_db()

        assert job.status == "completed"
        assert job.progress_percentage == 100
        assert job.segments.count() == 3
        assert job.srt_file.read().decode() == (
            "1\n00:00:00,000 --> 00:00:01,500\nOlá, mundo.\n\n"
            "2\n00:00:02,000 --> 00:01:05,123\nSegunda frase.\n"
        )
        assert job.vtt_file.read().decode().startswith("WEBVTT\n")
        assert job.transcript_file.read().decode() == " Olá, mundo.\n Segunda frase."
        assert job.json_file.name.endswith(".json")
        assert job.final_video.name.endswith("_with_subtitles.mp4")
        assert ffmpeg_ok.call_count == 2

    def test_audio_extraction_failure_marks_job_failed(
        self, job: TranscriptionJob, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = subprocess.CalledProcessError(1, ["ffmpeg"])
        monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=error))

        VideoProcessor(job).process()
        job.refresh_from_db()

        assert job.status == "failed"
        assert job.error_message == "Não foi possível extrair o áudio do arquivo."

    def test_transcription_failure_marks_job_failed(
        self, job: TranscriptionJob, ffmpeg_ok: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(utils.whisper, "load_model", MagicMock(side_effect=RuntimeError))

        VideoProcessor(job).process()
        job.refresh_from_db()

        assert job.status == "failed"
        assert job.error_message == "Falha ao transcrever o áudio."
        assert not SubtitleSegment.objects.filter(job=job).exists()


@pytest.mark.django_db
class TestTask:
    """The Celery task delegates to the processor and tolerates missing jobs."""

    def test_runs_processor(
        self, job: TranscriptionJob, ffmpeg_ok: MagicMock, whisper_ok: MagicMock
    ) -> None:
        process_video_task.apply(args=[str(job.id)])
        job.refresh_from_db()
        assert job.status == "completed"

    def test_missing_job_does_not_raise(self) -> None:
        result = process_video_task.apply(args=["00000000-0000-0000-0000-000000000000"])
        assert result.successful()
