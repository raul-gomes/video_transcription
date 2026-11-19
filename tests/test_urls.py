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


@pytest.mark.django_db
class TestMediaRanges:
    """The player can only seek when media answers byte ranges (HTTP 206)."""

    CONTENT = bytes(range(256)) * 4  # 1024 bytes

    @pytest.fixture(autouse=True)
    def _media(self, settings: Settings, tmp_path: Path) -> None:
        settings.MEDIA_ROOT = tmp_path
        (tmp_path / "videos").mkdir()
        (tmp_path / "videos" / "clip.mp4").write_bytes(self.CONTENT)

    def get(self, client: Client, range_header: str | None = None):  # noqa: ANN201 - test helper
        extra = {"HTTP_RANGE": range_header} if range_header else {}
        return client.get("/media/videos/clip.mp4", **extra)

    def test_full_file_advertises_ranges(self, client: Client) -> None:
        response = self.get(client)
        assert response.status_code == 200
        assert response["Accept-Ranges"] == "bytes"

    @pytest.mark.parametrize(
        ("header", "start", "end"),
        [("bytes=100-199", 100, 199), ("bytes=1000-", 1000, 1023), ("bytes=-24", 1000, 1023)],
    )
    def test_partial_content(self, client: Client, header: str, start: int, end: int) -> None:
        response = self.get(client, header)

        assert response.status_code == 206
        assert response["Content-Range"] == f"bytes {start}-{end}/1024"
        assert response["Content-Length"] == str(end - start + 1)
        assert b"".join(response.streaming_content) == self.CONTENT[start : end + 1]

    def test_end_past_the_file_is_clamped(self, client: Client) -> None:
        response = self.get(client, "bytes=1000-5000")
        assert response["Content-Range"] == "bytes 1000-1023/1024"

    @pytest.mark.parametrize("header", ["bytes=2000-", "bytes=-0"])
    def test_unsatisfiable_range(self, client: Client, header: str) -> None:
        response = self.get(client, header)
        assert response.status_code == 416
        assert response["Content-Range"] == "bytes */1024"

    @pytest.mark.parametrize("header", ["bytes=0-1,5-6", "items=0-1", "bytes=abc", "bytes=500-100"])
    def test_unsupported_range_falls_back_to_the_whole_file(
        self, client: Client, header: str
    ) -> None:
        response = self.get(client, header)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == self.CONTENT
