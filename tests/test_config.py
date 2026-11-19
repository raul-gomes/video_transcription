"""Tests for environment-driven configuration helpers."""

from pathlib import Path

import pytest

from video_transcription.config import env_bool, env_list, load_or_create_secret_key


class TestEnvBool:
    """env_bool parses common truthy/falsy spellings and falls back to the default."""

    @pytest.mark.parametrize("raw", ["1", "true", "True", "yes", "on"])
    def test_truthy_values(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("FLAG", raw)
        assert env_bool("FLAG", default=False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "False", "no", "off"])
    def test_falsy_values(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("FLAG", raw)
        assert env_bool("FLAG", default=True) is False

    def test_missing_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLAG", raising=False)
        assert env_bool("FLAG", default=True) is True

    def test_invalid_value_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLAG", "maybe")
        with pytest.raises(ValueError, match="FLAG"):
            env_bool("FLAG", default=False)


class TestEnvList:
    """env_list splits comma-separated values and ignores blanks."""

    def test_splits_and_strips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOSTS", " localhost, 127.0.0.1 ,,")
        assert env_list("HOSTS", default=["x"]) == ["localhost", "127.0.0.1"]

    def test_missing_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HOSTS", raising=False)
        assert env_list("HOSTS", default=["localhost"]) == ["localhost"]


class TestLoadOrCreateSecretKey:
    """The secret key comes from the environment or a generated file in the data dir."""

    def test_env_value_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
        assert load_or_create_secret_key(tmp_path / "secret_key") == "from-env"
        assert not (tmp_path / "secret_key").exists()

    def test_generates_and_persists(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
        path = tmp_path / "nested" / "secret_key"
        first = load_or_create_secret_key(path)
        assert len(first) >= 50
        assert path.stat().st_mode & 0o777 == 0o600
        assert load_or_create_secret_key(path) == first
