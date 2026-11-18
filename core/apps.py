"""App config for core."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Registers the worker signal handlers on startup."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        """Connect Celery worker hooks (no-op outside the worker)."""
        from . import worker  # noqa: F401 - imported for its signal connection
