"""HTTP layer: the page and the JSON API. Rules live in core/services.py."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .constants import ACCEPTED_EXTENSIONS, DEFAULT_LANGUAGE, LANGUAGES, WHISPER_MODELS
from .models import TranscriptionJob, WorkerState
from .permissions import CsrfProtected
from .serializers import DecisionSerializer, JobSerializer, SegmentSerializer, UploadSerializer
from .services import Decision, JobChoices, JobError, JobStateError


def index(request: HttpRequest) -> HttpResponse:
    """Render the single page (it embeds the CSRF token the API requires)."""
    return render(request, "core/index.html")


def _error(error: JobError) -> Response:
    """Turn a rule violation into 400 (bad input) or 409 (wrong status).

    Args:
        error: The service error.

    Returns:
        A response with the pt-BR message in ``detail``.
    """
    code = (
        status.HTTP_409_CONFLICT
        if isinstance(error, JobStateError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(error)}, status=code)


class BaseApiView(APIView):
    """API defaults: no login (local app, ADR 0001) and CSRF on every write."""

    authentication_classes: list = []
    permission_classes = [CsrfProtected]


class OptionsView(BaseApiView):
    """Choices and limits for the upload screen."""

    def get(self, request: Request) -> Response:
        """Return languages, models, defaults, limits and GPU availability."""
        return Response(
            {
                "languages": [{"code": lang.code, "label": lang.label} for lang in LANGUAGES],
                "models": [
                    {"name": model.name, "label": model.label, "hint": model.hint}
                    for model in WHISPER_MODELS
                ],
                "default_language": DEFAULT_LANGUAGE,
                "default_model": settings.WHISPER_DEFAULT_MODEL,
                "gpu_available": WorkerState.current().gpu_available,
                "max_upload_mb": settings.MAX_UPLOAD_MB,
                "accepted_extensions": sorted(ACCEPTED_EXTENSIONS),
            }
        )


class JobListView(BaseApiView):
    """History list and upload."""

    def get(self, request: Request) -> Response:
        """Return every job, newest first."""
        return Response(JobSerializer(services.list_jobs(), many=True).data)

    def post(self, request: Request) -> Response:
        """Create a job from an uploaded file and the chosen options."""
        form = UploadSerializer(data=request.data)
        if not form.is_valid():
            return Response(
                {"detail": "Envie um arquivo de vídeo ou áudio.", "fields": form.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = form.validated_data
        choices = JobChoices(
            language=data["language"],
            model=data.get("model") or settings.WHISPER_DEFAULT_MODEL,
            device=data["device"],
        )
        try:
            job = services.create_job(data["media"], choices)
        except JobError as error:
            return _error(error)
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


class JobDetailView(BaseApiView):
    """One job: delete."""

    def delete(self, request: Request, job_id: str) -> Response:
        """Delete a finished job and its files."""
        job = get_object_or_404(TranscriptionJob, pk=job_id)
        try:
            services.delete_job(job)
        except JobError as error:
            return _error(error)
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobConfirmView(BaseApiView):
    """Confirm the Análise da Mídia decision and queue the job."""

    def post(self, request: Request, job_id: str) -> Response:
        """Record track, language, model, device and preview; return the queued job."""
        job = get_object_or_404(TranscriptionJob, pk=job_id)
        form = DecisionSerializer(data=request.data)
        if not form.is_valid():
            return Response(
                {"detail": "Decisão inválida.", "fields": form.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            services.confirm_job(job, Decision(**form.validated_data))
        except JobError as error:
            return _error(error)
        return Response(JobSerializer(job).data)


class JobCancelView(BaseApiView):
    """Cancel a queued or running job."""

    def post(self, request: Request, job_id: str) -> Response:
        """Cancel and return the updated job."""
        job = get_object_or_404(TranscriptionJob, pk=job_id)
        try:
            services.cancel_job(job)
        except JobError as error:
            return _error(error)
        return Response(JobSerializer(job).data)


class JobRetryView(BaseApiView):
    """Send a failed, cancelled or interrupted job back to the queue."""

    def post(self, request: Request, job_id: str) -> Response:
        """Requeue and return the updated job."""
        job = get_object_or_404(TranscriptionJob, pk=job_id)
        try:
            services.retry_job(job)
        except JobError as error:
            return _error(error)
        return Response(JobSerializer(job).data)


class JobSegmentsView(BaseApiView):
    """Transcript segments of a job, for the live view."""

    def get(self, request: Request, job_id: str) -> Response:
        """Return segments starting after ``?after=<seconds>`` (default: all)."""
        job = get_object_or_404(TranscriptionJob, pk=job_id)
        raw = request.query_params.get("after", "-1")
        try:
            after = float(raw)
        except ValueError:
            return Response(
                {"detail": "Parâmetro 'after' inválido."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(SegmentSerializer(services.segments_after(job, after), many=True).data)
