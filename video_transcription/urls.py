"""Project URL configuration."""

import re
from collections.abc import Iterator
from typing import BinaryIO

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest, HttpResponse, HttpResponseBase, StreamingHttpResponse
from django.urls import include, path, re_path
from django.views.static import serve

#: A single byte range: ``bytes=first-last``, ``bytes=first-`` or ``bytes=-suffix``.
SINGLE_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
#: Size of each read while streaming part of a file.
RANGE_CHUNK_BYTES = 64 * 1024


def parse_range(header: str, size: int) -> tuple[int, int] | None | bool:
    """Resolve a ``Range`` header against a file size (RFC 7233, single range only).

    Args:
        header: Value of the ``Range`` request header.
        size: File size in bytes.

    Returns:
        ``(first, last)`` inclusive for a satisfiable range; ``False`` when the range
        is valid but outside the file (answer 416); ``None`` when the header is
        unsupported or invalid and must be ignored (answer the whole file).
    """
    match = SINGLE_RANGE.match(header.strip())
    if not match or match.groups() == ("", ""):
        return None
    first, last = match.groups()
    if first == "":
        suffix = int(last)
        if suffix == 0:
            return False
        return max(size - suffix, 0), size - 1
    start = int(first)
    if last != "" and int(last) < start:
        return None
    if start >= size:
        return False
    end = size - 1 if last == "" else int(last)
    return start, min(end, size - 1)


def _stream(file: BinaryIO, start: int, length: int) -> Iterator[bytes]:
    """Yield ``length`` bytes of ``file`` from ``start``, then close it."""
    try:
        file.seek(start)
        remaining = length
        while remaining > 0:
            chunk = file.read(min(RANGE_CHUNK_BYTES, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file.close()


def serve_media(request: HttpRequest, path: str) -> HttpResponseBase:
    """Serve a generated file from MEDIA_ROOT, answering byte ranges so the player can seek.

    Args:
        request: Incoming request.
        path: File path relative to MEDIA_ROOT.

    Returns:
        The whole file (200), the requested part (206) or 416 for a range outside the
        file. ``serve`` raises 404 for missing or escaping paths.
    """
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["Accept-Ranges"] = "bytes"
    header = request.headers.get("Range")
    if not header or response.status_code != 200:
        return response
    size = int(response["Content-Length"])
    resolved = parse_range(header, size)
    if resolved is None:
        return response
    file = response.file_to_stream
    if resolved is False:
        file.close()
        refused = HttpResponse(status=416)
        refused["Content-Range"] = f"bytes */{size}"
        return refused
    start, end = resolved
    length = end - start + 1
    partial = StreamingHttpResponse(
        _stream(file, start, length), status=206, content_type=response["Content-Type"]
    )
    partial["Content-Range"] = f"bytes {start}-{end}/{size}"
    partial["Content-Length"] = str(length)
    partial["Accept-Ranges"] = "bytes"
    return partial


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    # Generated files (subtitles, transcripts, videos) are downloaded straight from
    # MEDIA_ROOT. Acceptable because the app is local and loopback-only (ADR 0001);
    # `serve` rejects paths that escape MEDIA_ROOT.
    re_path(r"^media/(?P<path>.*)$", serve_media),
]
