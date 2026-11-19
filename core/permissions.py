"""CSRF protection for the API.

The app has no login, so DRF's session authentication (the usual CSRF trigger)
never runs. Without this check any website open in the browser could post to
127.0.0.1 and upload, cancel or delete jobs.
"""

from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class _CsrfCheck(CsrfViewMiddleware):
    """CsrfViewMiddleware that returns the failure reason instead of a response."""

    def _reject(self, request: HttpRequest, reason: str) -> str:  # type: ignore[override]
        return reason


def _no_response(request: HttpRequest) -> HttpResponse:
    """Placeholder get_response; never called by process_view."""
    raise NotImplementedError


class CsrfProtected(BasePermission):
    """Require a valid CSRF token on every unsafe method."""

    message = "Requisição sem token CSRF válido. Recarregue a página."

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Allow safe methods; check the CSRF token on the others."""
        if request.method in SAFE_METHODS:
            return True
        check = _CsrfCheck(_no_response)
        check.process_request(request._request)  # noqa: SLF001 - DRF wraps the Django request
        reason = check.process_view(request._request, None, (), {})  # noqa: SLF001
        return reason is None
