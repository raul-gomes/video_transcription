"""Project URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpRequest
from django.urls import include, path, re_path
from django.views.static import serve


def serve_media(request: HttpRequest, path: str) -> FileResponse:
    """Serve a generated file from MEDIA_ROOT, read at request time.

    Args:
        request: Incoming request.
        path: File path relative to MEDIA_ROOT.

    Returns:
        The file response (``serve`` raises 404 for missing or escaping paths).
    """
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    # Generated files (subtitles, transcripts, videos) are downloaded straight from
    # MEDIA_ROOT. Acceptable because the app is local and loopback-only (ADR 0001);
    # `serve` rejects paths that escape MEDIA_ROOT.
    re_path(r"^media/(?P<path>.*)$", serve_media),
]
