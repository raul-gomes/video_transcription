"""Tests for the job service layer (business rules behind the API)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from pytest_django.fixtures import Settings

from core import services
from core.models import JobStatus, SubtitleSegment, TranscriptionJob, WorkerState
from core.services import JobChoices, JobError

pytestmark = pytest.mark.django_db

DEFAULT_CHOICES = JobChoices(language="pt", model="small", device="auto")


@pytest.fixture(autouse=True)
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def enqueue(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the Celery enqueue call and return a fake task id."""
    fake = MagicMock(return_value=MagicMock(id="task-123"))
    monkeypatch.setattr(services.process_video_task, "apply_async", fake)
    return fake


@pytest.fixture
def on_commit(django_capture_on_commit_callbacks):
    """Run transaction.on_commit callbacks (the test transaction never commits)."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


@pytest.fixture
def revoke(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace Celery's revoke so no broker is contacted."""
    fake = MagicMock()
    monkeypatch.setattr(services.celery_app.control, "revoke", fake)
    return fake


def upload(name: str = "clip.mp4", size: int = 4) -> SimpleUploadedFile:
    """A fake uploaded file with ``size`` bytes."""
    return SimpleUploadedFile(name, b"x" * size)


def make_job(status: str = JobStatus.COMPLETED, **fields: object) -> TranscriptionJob:
    """A job with a media file and every generated file on disk."""
    job = TranscriptionJob(status=status, original_filename="clip.mp4", **fields)
    job.media_file.save("clip.mp4", ContentFile(b"media"), save=False)
    for field in ("audio_file", "srt_file", "vtt_file", "json_file", "transcript_file"):
        getattr(job, field).save(f"out-{field}.txt", ContentFile(b"out"), save=False)
    job.final_video.save("final.mp4", ContentFile(b"final"), save=False)
    job.save()
    SubtitleSegment.objects.create(job=job, start_time=0, end_time=1, text="Oi")
    return job


class TestCreateJob:
    def test_creates_queued_job_and_enqueues(self, enqueue: MagicMock, on_commit) -> None:
        with on_commit():
            job = services.create_job(upload("Aula 1.MP4"), JobChoices("en", "tiny", "cpu"))
        job.refresh_from_db()

        assert job.status == JobStatus.QUEUED
        assert job.original_filename == "Aula 1.MP4"
        assert job.media_kind == "video"
        assert (job.language, job.model_name, job.device) == ("en", "tiny", "cpu")
        assert job.celery_task_id == "task-123"
        enqueue.assert_called_once_with(args=[str(job.id)])

    def test_audio_extension_is_audio_media(self, enqueue: MagicMock) -> None:
        job = services.create_job(upload("podcast.mp3"), DEFAULT_CHOICES)
        assert job.media_kind == "audio"

    def test_rejects_unsupported_extension(self, enqueue: MagicMock) -> None:
        with pytest.raises(JobError, match=r"\.avi"):
            services.create_job(upload("old.avi"), DEFAULT_CHOICES)
        assert not TranscriptionJob.objects.exists()

    def test_rejects_file_over_the_limit(self, enqueue: MagicMock, settings: Settings) -> None:
        settings.MAX_UPLOAD_MB = 1
        with pytest.raises(JobError, match="1 MB"):
            services.create_job(upload(size=1024 * 1024 + 1), DEFAULT_CHOICES)

    @pytest.mark.parametrize(
        "choices",
        [
            JobChoices("xx", "small", "auto"),
            JobChoices("pt", "huge", "auto"),
            JobChoices("pt", "small", "tpu"),
        ],
    )
    def test_rejects_unknown_choices(self, enqueue: MagicMock, choices: JobChoices) -> None:
        with pytest.raises(JobError):
            services.create_job(upload(), choices)

    def test_rejects_gpu_when_worker_has_none(self, enqueue: MagicMock) -> None:
        with pytest.raises(JobError, match="GPU"):
            services.create_job(upload(), JobChoices("pt", "small", "gpu"))

    def test_accepts_gpu_when_worker_has_one(self, enqueue: MagicMock) -> None:
        WorkerState.objects.update_or_create(pk=1, defaults={"gpu_available": True})
        job = services.create_job(upload(), JobChoices("pt", "small", "gpu"))
        assert job.device == "gpu"


class TestCancelJob:
    def test_queued_job_is_revoked_without_killing(self, revoke: MagicMock) -> None:
        job = make_job(JobStatus.QUEUED, celery_task_id="t1")

        services.cancel_job(job)

        job.refresh_from_db()
        assert job.status == JobStatus.CANCELLED
        revoke.assert_called_once_with("t1", terminate=False)

    def test_running_job_is_terminated(self, revoke: MagicMock) -> None:
        job = make_job(JobStatus.TRANSCRIBING, celery_task_id="t2")

        services.cancel_job(job)

        revoke.assert_called_once_with("t2", terminate=True, signal="SIGTERM")
        job.refresh_from_db()
        assert job.current_step == "Cancelado pela pessoa"

    def test_finished_job_cannot_be_cancelled(self, revoke: MagicMock) -> None:
        with pytest.raises(JobError):
            services.cancel_job(make_job(JobStatus.COMPLETED))
        revoke.assert_not_called()


class TestRetryJob:
    @pytest.mark.parametrize(
        "status", [JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.INTERRUPTED]
    )
    def test_resets_outputs_and_requeues(
        self,
        enqueue: MagicMock,
        on_commit,
        status: str,
    ) -> None:
        job = make_job(status, error_message="boom", progress_percentage=40)
        old_srt = Path(job.srt_file.path)

        with on_commit():
            services.retry_job(job)

        job.refresh_from_db()
        assert job.status == JobStatus.QUEUED
        assert (job.progress_percentage, job.error_message) == (0, "")
        assert not job.srt_file and not old_srt.exists()
        assert not job.segments.exists()
        assert Path(job.media_file.path).exists()
        enqueue.assert_called_once_with(args=[str(job.id)])

    def test_completed_job_cannot_be_retried(self, enqueue: MagicMock) -> None:
        with pytest.raises(JobError):
            services.retry_job(make_job(JobStatus.COMPLETED))


class TestDeleteJob:
    def test_removes_row_and_every_file(self, media_root: Path) -> None:
        job = make_job(JobStatus.COMPLETED)

        services.delete_job(job)

        assert not TranscriptionJob.objects.exists()
        assert [p for p in media_root.rglob("*") if p.is_file()] == []

    def test_active_job_cannot_be_deleted(self) -> None:
        with pytest.raises(JobError):
            services.delete_job(make_job(JobStatus.TRANSCRIBING))


class TestWorkerStarted:
    def test_records_gpu_and_interrupts_running_jobs(self) -> None:
        running = make_job(JobStatus.TRANSCRIBING)
        queued = make_job(JobStatus.QUEUED)
        done = make_job(JobStatus.COMPLETED)

        services.worker_started(gpu_available=True)

        assert WorkerState.current().gpu_available is True
        running.refresh_from_db()
        queued.refresh_from_db()
        done.refresh_from_db()
        assert running.status == JobStatus.INTERRUPTED
        assert running.current_step == "O app foi fechado durante o processamento"
        assert queued.status == JobStatus.QUEUED
        assert done.status == JobStatus.COMPLETED


class TestSegmentsAfter:
    def test_returns_only_later_segments_in_order(self) -> None:
        job = make_job(JobStatus.TRANSCRIBING)
        SubtitleSegment.objects.create(job=job, start_time=5, end_time=6, text="b")
        SubtitleSegment.objects.create(job=job, start_time=2, end_time=3, text="a")

        texts = [segment.text for segment in services.segments_after(job, after=1.0)]

        assert texts == ["a", "b"]


def test_worker_ready_hook_reports_gpu_without_touching_cuda_in_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initialising CUDA in the parent breaks every forked child (prefork pool)."""
    from core import utils, worker

    def forbidden() -> bool:
        raise AssertionError("CUDA must not be initialised in the worker's main process")

    monkeypatch.setattr(utils, "cuda_available", forbidden)
    monkeypatch.setattr(utils, "detect_gpu_in_subprocess", lambda: True)

    worker.on_worker_ready()

    assert WorkerState.current().gpu_available is True
