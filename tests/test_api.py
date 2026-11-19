"""Tests for the JSON API consumed by static/js/api.js (contract in static/js/contract.js)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from pytest_django.fixtures import Settings

from core import services
from core.media_analysis import parse_probe
from core.models import JobStatus, SubtitleSegment, TranscriptionJob, WorkerState
from tests.fixtures.probes import DUAL_AUDIO_MKV

pytestmark = pytest.mark.django_db

JOB_KEYS = {
    "id",
    "filename",
    "media_kind",
    "status",
    "progress",
    "step_label",
    "error",
    "language",
    "model",
    "device",
    "created_at",
    "duration_seconds",
    "files",
    "analysis",
}


@pytest.fixture(autouse=True)
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture(autouse=True)
def celery(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """No broker: enqueue and revoke are fakes."""
    monkeypatch.setattr(
        services.process_video_task, "apply_async", MagicMock(return_value=MagicMock(id="t"))
    )
    revoke = MagicMock()
    monkeypatch.setattr(services.celery_app.control, "revoke", revoke)
    return revoke


@pytest.fixture(autouse=True)
def analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake Análise da Mídia (no ffprobe in tests)."""
    result = parse_probe(DUAL_AUDIO_MKV, extension="mkv")
    monkeypatch.setattr(services, "analyze", lambda path: result)


@pytest.fixture
def csrf_client() -> Client:
    """A client that enforces CSRF like a real browser."""
    return Client(enforce_csrf_checks=True)


def make_job(status: str = JobStatus.COMPLETED) -> TranscriptionJob:
    """A job with a media file and an SRT."""
    job = TranscriptionJob(status=status, original_filename="aula.mp4", model_name="tiny")
    job.media_file.save("aula.mp4", ContentFile(b"m"), save=False)
    job.srt_file.save("aula.srt", ContentFile(b"s"), save=False)
    job.save()
    return job


class TestIndex:
    def test_renders_page_with_csrf_token(self, client: Client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert b'name="csrf-token"' in response.content


class TestOptions:
    def test_lists_choices_and_limits(self, client: Client, settings: Settings) -> None:
        settings.WHISPER_DEFAULT_MODEL = "base"
        settings.MAX_UPLOAD_MB = 100
        WorkerState.objects.update_or_create(pk=1, defaults={"gpu_available": True})

        body = client.get("/api/options/").json()

        assert body["default_model"] == "base"
        assert body["default_language"] == "pt"
        assert body["max_upload_mb"] == 100
        assert body["gpu_available"] is True
        assert {"code": "auto", "label": "Detectar automaticamente"} in body["languages"]
        assert [m["name"] for m in body["models"]] == ["tiny", "base", "small", "medium", "large"]
        assert "mp3" in body["accepted_extensions"]


class TestJobs:
    def test_list_matches_the_contract(self, client: Client) -> None:
        job = make_job()

        body = client.get("/api/jobs/").json()

        assert len(body) == 1
        item = body[0]
        assert set(item) == JOB_KEYS
        assert item["id"] == str(job.id)
        assert item["filename"] == "aula.mp4"
        assert item["model"] == "tiny"
        assert item["step_label"] == "Concluído"
        assert item["files"]["media"].startswith("/media/videos/")
        assert item["files"]["srt"].startswith("/media/subtitles/")
        assert item["files"]["video"] is None
        assert item["files"]["preview"] is None
        assert item["analysis"] is None

    def test_upload_creates_a_queued_job(self, csrf_client: Client) -> None:
        token = csrf_client.get("/").cookies["csrftoken"].value
        media = SimpleUploadedFile("Aula.mp4", b"data")

        response = csrf_client.post(
            "/api/jobs/",
            {"media": media, "language": "en", "model": "base", "device": "cpu"},
            HTTP_X_CSRFTOKEN=token,
        )

        assert response.status_code == 201, response.content
        body = response.json()
        assert body["status"] == "awaiting_decision"
        assert [t["index"] for t in body["analysis"]["audio_tracks"]] == [1, 2]
        assert TranscriptionJob.objects.get().language == "en"

    def test_upload_rule_errors_are_400_with_message(self, client: Client) -> None:
        response = client.post("/api/jobs/", {"media": SimpleUploadedFile("a.avi", b"x")})
        assert response.status_code == 400
        assert ".avi" in response.json()["detail"]

    def test_upload_without_file_is_400(self, client: Client) -> None:
        response = client.post("/api/jobs/", {})
        assert response.status_code == 400

    def test_writes_without_csrf_token_are_rejected(self, csrf_client: Client) -> None:
        job = make_job()
        assert csrf_client.delete(f"/api/jobs/{job.id}/").status_code == 403
        assert TranscriptionJob.objects.filter(pk=job.pk).exists()

    def test_delete(self, client: Client) -> None:
        job = make_job()
        assert client.delete(f"/api/jobs/{job.id}/").status_code == 204
        assert not TranscriptionJob.objects.exists()

    def test_delete_active_job_is_409(self, client: Client) -> None:
        job = make_job(JobStatus.TRANSCRIBING)
        response = client.delete(f"/api/jobs/{job.id}/")
        assert response.status_code == 409
        assert response.json()["detail"]

    def test_cancel(self, client: Client) -> None:
        job = make_job(JobStatus.QUEUED)
        response = client.post(f"/api/jobs/{job.id}/cancel/")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_retry(self, client: Client) -> None:
        job = make_job(JobStatus.FAILED)
        response = client.post(f"/api/jobs/{job.id}/retry/")
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_unknown_job_is_404(self, client: Client) -> None:
        url = "/api/jobs/00000000-0000-0000-0000-000000000000/cancel/"
        assert client.post(url).status_code == 404


class TestConfirm:
    def make_awaiting(self, client: Client) -> str:
        response = client.post("/api/jobs/", {"media": SimpleUploadedFile("ep.mkv", b"x")})
        return response.json()["id"]

    def test_confirm_queues_the_job(self, client: Client) -> None:
        job_id = self.make_awaiting(client)

        response = client.post(
            f"/api/jobs/{job_id}/confirm/",
            {"audio_track": 2, "language": "en", "model": "tiny", "device": "cpu",
             "preview": True, "convert_video": False},
            content_type="application/json",
        )  # fmt: skip

        assert response.status_code == 200, response.content
        assert response.json()["status"] == "queued"
        job = TranscriptionJob.objects.get(pk=job_id)
        assert (job.audio_stream_index, job.make_preview) == (2, True)

    def test_invalid_body_is_400(self, client: Client) -> None:
        job_id = self.make_awaiting(client)
        response = client.post(
            f"/api/jobs/{job_id}/confirm/", {"audio_track": "x"}, content_type="application/json"
        )
        assert response.status_code == 400

    def test_confirm_twice_is_409(self, client: Client) -> None:
        job = make_job(JobStatus.QUEUED)
        response = client.post(
            f"/api/jobs/{job.id}/confirm/",
            {"audio_track": 1, "language": "pt", "model": "small", "device": "auto",
             "preview": False, "convert_video": False},
            content_type="application/json",
        )  # fmt: skip
        assert response.status_code == 409


class TestSegments:
    def test_returns_segments_after_offset(self, client: Client) -> None:
        job = make_job(JobStatus.TRANSCRIBING)
        SubtitleSegment.objects.create(job=job, start_time=0, end_time=1, text=" a")
        SubtitleSegment.objects.create(job=job, start_time=4, end_time=5, text=" b")

        body = client.get(f"/api/jobs/{job.id}/segments/?after=1").json()

        assert body == [{"start": 4.0, "end": 5.0, "text": " b"}]

    def test_invalid_offset_is_400(self, client: Client) -> None:
        job = make_job()
        assert client.get(f"/api/jobs/{job.id}/segments/?after=abc").status_code == 400


def test_page_loads_nothing_from_the_internet(client: Client) -> None:
    """The app promises that nothing leaves the machine: no CDN assets."""
    import re

    html = client.get("/").content.decode()
    external = re.findall(r'<(?:link|script)[^>]+(?:href|src)="(https?://[^"]+)"', html)
    assert external == []

    from django.conf import settings

    for css in (settings.BASE_DIR / "static").rglob("*.css"):
        urls = re.findall(r"url\(\s*['\"]?(https?://[^'\")]+)", css.read_text())
        assert urls == [], f"{css.name} loads {urls}"
