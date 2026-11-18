"""Characterization tests for the current HTTP endpoints."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from pytest_django.fixtures import Settings

from core import views
from core.models import TranscriptionJob


@pytest.fixture(autouse=True)
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.mark.django_db
class TestIndex:
    def test_renders_page(self, client: Client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert b"<html" in response.content.lower()


@pytest.mark.django_db
class TestUpload:
    def test_missing_file_is_rejected(self, client: Client) -> None:
        response = client.post("/api/upload/")
        assert response.status_code == 400
        assert response.json() == {"error": "No video file provided"}

    def test_creates_job_and_enqueues(
        self, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        enqueue = MagicMock()
        monkeypatch.setattr(views.process_video_task, "delay", enqueue)
        upload = SimpleUploadedFile("clip.mp4", b"fake", content_type="video/mp4")

        response = client.post("/api/upload/", {"video_file": upload})

        assert response.status_code == 200
        job = TranscriptionJob.objects.get()
        assert response.json()["job_id"] == str(job.id)
        enqueue.assert_called_once_with(str(job.id))


@pytest.mark.django_db
class TestProgress:
    def test_unknown_job_is_404(self, client: Client) -> None:
        response = client.get("/api/progress/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404

    def test_reports_status_and_files(self, client: Client) -> None:
        job = TranscriptionJob.objects.create(
            video_file="videos/clip.mp4", status="transcribing", progress_percentage=60
        )

        response = client.get(f"/api/progress/{job.id}/")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "transcribing"
        assert body["progress_percentage"] == 60
        assert body["file"] == {"srt": None, "vtt": None, "transcript": None, "video": None}
