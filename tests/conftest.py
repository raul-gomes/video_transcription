"""Shared test setup: isolate the app data directory from the developer's machine."""

import os
import tempfile

# Must run before Django settings are imported, so the test run never touches ./data.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="vt-test-data-"))
os.environ.pop("DJANGO_DEBUG", None)
# Celery talks to in-memory transports in tests: no Redis needed.
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
