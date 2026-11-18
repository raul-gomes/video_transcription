"""Tests for project-level URL wiring."""

from pathlib import Path

import pytest
from django.test import Client
from pytest_django.fixtures import Settings


def test_debug_is_off_by_default(settings: Settings) -> None:
    assert settings.DEBUG is False


@pytest.mark.django_db
def test_media_files_are_served_without_debug(
    client: Client, settings: Settings, tmp_path: Path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "subtitles").mkdir()
    (tmp_path / "subtitles" / "job.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nOi\n")

    response = client.get("/media/subtitles/job.srt")

    assert response.status_code == 200
    assert b"Oi" in b"".join(response.streaming_content)


@pytest.mark.django_db
def test_media_rejects_path_traversal(client: Client, settings: Settings, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    (tmp_path / "secret.txt").write_text("nope")

    response = client.get("/media/../secret.txt")

    assert response.status_code in {400, 404}
    assert b"nope" not in response.content
