"""Helpers that read configuration from environment variables."""

import os
import secrets
from pathlib import Path

TRUTHY = frozenset({"1", "true", "yes", "on"})
FALSY = frozenset({"0", "false", "no", "off"})
SECRET_KEY_BYTES = 50
SECRET_FILE_MODE = 0o600


def env_bool(name: str, *, default: bool) -> bool:
    """Read a boolean environment variable.

    Args:
        name: Variable name.
        default: Value used when the variable is not set.

    Returns:
        The parsed boolean.

    Raises:
        ValueError: If the value is not a recognised boolean spelling.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in TRUTHY:
        return True
    if value in FALSY:
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def env_list(name: str, *, default: list[str]) -> list[str]:
    """Read a comma-separated environment variable as a list.

    Args:
        name: Variable name.
        default: Value used when the variable is not set.

    Returns:
        The non-empty, stripped items.
    """
    raw = os.environ.get(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_or_create_secret_key(path: Path) -> str:
    """Return the Django secret key from the environment or a local file.

    When ``DJANGO_SECRET_KEY`` is not set, a random key is generated on first
    use and stored at ``path`` with owner-only permissions, so each local
    install has its own key without manual setup.

    Args:
        path: File where the generated key is stored.

    Returns:
        The secret key.
    """
    from_env = os.environ.get("DJANGO_SECRET_KEY")
    if from_env:
        return from_env
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(SECRET_KEY_BYTES)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, SECRET_FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(key)
    return key
