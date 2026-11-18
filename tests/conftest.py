"""Shared test setup: isolate the app data directory from the developer's machine."""

import os
import tempfile

# Must run before Django settings are imported, so the test run never touches ./data.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="vt-test-data-"))
os.environ.pop("DJANGO_DEBUG", None)
# Celery talks to in-memory transports in tests: no Redis needed.
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")


import pytest  # noqa: E402  (env vars above must be set before anything imports Django)


@pytest.fixture(autouse=True)
def _clear_whisper_model_cache() -> None:
    """Each test starts with no Whisper model loaded in the worker cache."""
    from core.utils import clear_model_cache

    clear_model_cache()
