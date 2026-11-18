"""Job business rules. Views call these; they never touch models or Celery directly."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePath

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet
from loguru import logger

from video_transcription.celery import app as celery_app

from .constants import (
    ACCEPTED_EXTENSIONS,
    AUDIO_EXTENSIONS,
    BYTES_PER_MB,
    DEVICE_GPU,
    DEVICES,
    LANGUAGE_CODES,
    WHISPER_MODEL_NAMES,
)
from .media_analysis import AnalysisError, analyze
from .models import (
    ACTIVE_STATUSES,
    RETRYABLE_STATUSES,
    RUNNING_STATUSES,
    JobStatus,
    MediaKind,
    SubtitleSegment,
    TranscriptionJob,
    WorkerState,
)
from .tasks import process_video_task

GENERATED_FILE_FIELDS = (
    "preview_file",
    "audio_file",
    "srt_file",
    "vtt_file",
    "json_file",
    "transcript_file",
    "final_video",
)
AWAITING_STEP = "Confira a análise do arquivo"
QUEUED_STEP = "Aguardando a vez"
CANCELLED_STEP = "Cancelado pela pessoa"
INTERRUPTED_STEP = "O app foi fechado durante o processamento"


class JobError(Exception):
    """A request that breaks a job rule. The message is pt-BR and safe to show."""


class JobStateError(JobError):
    """The action is not allowed in the job's current status."""


@dataclass(frozen=True)
class JobChoices:
    """Per-job options picked on the upload screen."""

    language: str
    model: str
    device: str


@dataclass(frozen=True)
class Decision:
    """What the person confirmed in the Análise da Mídia modal."""

    audio_track: int
    language: str
    model: str
    device: str
    preview: bool
    convert_video: bool


def create_job(media: UploadedFile, choices: JobChoices) -> TranscriptionJob:
    """Validate and store an upload, analyse it and wait for the person's decision.

    The job does not enter the queue here: it stays ``awaiting_decision`` until
    ``confirm_job`` (ADR 0007).

    Args:
        media: The uploaded video or audio file.
        choices: Language, Whisper model and device picked on the upload card.

    Returns:
        The saved job, with its Análise da Mídia.

    Raises:
        JobError: If the file or the choices are not accepted, or the file is unusable.
    """
    extension = PurePath(media.name or "").suffix.lower().lstrip(".")
    if extension not in ACCEPTED_EXTENSIONS:
        raise JobError(f"Formato .{extension or '?'} não suportado.")
    max_mb = settings.MAX_UPLOAD_MB
    if media.size > max_mb * BYTES_PER_MB:
        raise JobError(f"Arquivo maior que o limite de {max_mb} MB.")
    _validate_choices(choices.language, choices.model, choices.device, check_gpu=False)

    job = TranscriptionJob(
        original_filename=PurePath(media.name).name,
        media_kind=MediaKind.AUDIO if extension in AUDIO_EXTENSIONS else MediaKind.VIDEO,
        language=choices.language,
        model_name=choices.model,
        device=choices.device,
        status=JobStatus.AWAITING_DECISION,
        current_step=AWAITING_STEP,
    )
    job.media_file.save(f"{job.id}.{extension}", media, save=False)
    try:
        job.analysis = analyze(job.media_file.path)
    except AnalysisError as error:
        job.media_file.delete(save=False)
        raise JobError(str(error)) from error
    job.save()
    return job


def confirm_job(job: TranscriptionJob, decision: Decision) -> None:
    """Record the person's decision and send the job to the queue.

    Args:
        job: A job awaiting a decision.
        decision: Track, language, model, device and preview choices.

    Raises:
        JobStateError: If the job is not awaiting a decision.
        JobError: If the track or the choices are not valid.
    """
    if job.status != JobStatus.AWAITING_DECISION:
        raise JobStateError("Este arquivo já foi confirmado.")
    tracks = {track["index"] for track in (job.analysis or {}).get("audio_tracks", [])}
    if decision.audio_track not in tracks:
        raise JobError("Faixa de áudio não encontrada no arquivo.")
    _validate_choices(decision.language, decision.model, decision.device, check_gpu=True)
    job.audio_stream_index = decision.audio_track
    job.language = decision.language
    job.model_name = decision.model
    job.device = decision.device
    job.make_preview = decision.preview
    job.convert_video = decision.preview and decision.convert_video
    job.status = JobStatus.QUEUED
    job.current_step = QUEUED_STEP
    job.save()
    _enqueue(job)


def _validate_choices(language: str, model: str, device: str, *, check_gpu: bool) -> None:
    """Reject unknown options and, when asked, a GPU the worker does not have.

    Args:
        language: Language code.
        model: Whisper model size.
        device: auto, cpu or gpu.
        check_gpu: Also require a detected GPU when ``device`` is gpu.

    Raises:
        JobError: On the first invalid option.
    """
    if language not in LANGUAGE_CODES:
        raise JobError("Idioma não suportado.")
    if model not in WHISPER_MODEL_NAMES:
        raise JobError("Modelo do Whisper desconhecido.")
    if device not in DEVICES:
        raise JobError("Dispositivo desconhecido.")
    if check_gpu and device == DEVICE_GPU and not WorkerState.current().gpu_available:
        raise JobError("GPU indisponível. Inicie o app com o arquivo docker-compose.gpu.yml.")


def _enqueue(job: TranscriptionJob) -> None:
    """Send the job to the worker queue once the database commit is visible.

    Args:
        job: A saved, queued job.
    """

    def send() -> None:
        result = process_video_task.apply_async(args=[str(job.id)])
        TranscriptionJob.objects.filter(pk=job.pk).update(celery_task_id=result.id)
        job.celery_task_id = result.id

    transaction.on_commit(send, robust=False)


def list_jobs() -> QuerySet[TranscriptionJob]:
    """All jobs, newest first."""
    return TranscriptionJob.objects.all()


def cancel_job(job: TranscriptionJob) -> None:
    """Stop a queued or running job. Segments already transcribed are kept.

    Args:
        job: The job to cancel.

    Raises:
        JobError: If the job is not waiting or running.
    """
    if job.status not in ACTIVE_STATUSES:
        raise JobStateError("Só dá para cancelar o que está na fila ou em andamento.")
    running = job.status in RUNNING_STATUSES
    job.status = JobStatus.CANCELLED
    job.current_step = CANCELLED_STEP
    job.save(update_fields=["status", "current_step", "updated_at"])
    if job.celery_task_id:
        if running:
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")
        else:
            celery_app.control.revoke(job.celery_task_id, terminate=False)
    logger.info(f"[{job.id}] Cancelled (was running: {running}).")


def retry_job(job: TranscriptionJob) -> None:
    """Send a failed, cancelled or interrupted job back to the queue from scratch.

    Args:
        job: The job to reprocess.

    Raises:
        JobError: If the job is not in a retryable status.
    """
    if job.status not in RETRYABLE_STATUSES:
        raise JobStateError("Só dá para reprocessar o que falhou, foi cancelado ou interrompido.")
    _delete_files(job, GENERATED_FILE_FIELDS)
    job.segments.all().delete()
    job.status = JobStatus.QUEUED
    job.progress_percentage = 0
    job.current_step = QUEUED_STEP
    job.error_message = ""
    job.duration_seconds = None
    job.save()
    _enqueue(job)


def delete_job(job: TranscriptionJob) -> None:
    """Delete a finished job and every file it owns from disk.

    Args:
        job: The job to delete.

    Raises:
        JobError: If the job is still waiting or running.
    """
    if job.is_active:
        raise JobStateError("Cancele o processamento antes de excluir.")
    _delete_files(job, ("media_file", *GENERATED_FILE_FIELDS))
    job.delete()


def _delete_files(job: TranscriptionJob, fields: Iterable[str]) -> None:
    """Remove the files behind ``fields`` from storage and clear the fields.

    Args:
        job: The job owning the files.
        fields: FileField names to clear.
    """
    for field in fields:
        stored = getattr(job, field)
        if stored:
            stored.delete(save=False)


def worker_started(*, gpu_available: bool) -> None:
    """Record what a starting worker found and flag jobs it can no longer finish.

    A job that was running when the app stopped stays ``interrupted`` until the
    person reprocesses it. Queued jobs keep waiting for their broker message.

    Args:
        gpu_available: Whether the worker can use an NVIDIA GPU.
    """
    WorkerState.objects.update_or_create(
        pk=WorkerState.SINGLETON_ID, defaults={"gpu_available": gpu_available}
    )
    interrupted = TranscriptionJob.objects.filter(status__in=RUNNING_STATUSES).update(
        status=JobStatus.INTERRUPTED, current_step=INTERRUPTED_STEP
    )
    logger.info(f"Worker started (GPU: {gpu_available}); {interrupted} job(s) interrupted.")


def segments_after(job: TranscriptionJob, after: float) -> QuerySet[SubtitleSegment]:
    """Segments of ``job`` that start after ``after`` seconds, in time order.

    Args:
        job: The job.
        after: Lower bound in seconds (exclusive).

    Returns:
        The matching segments.
    """
    return job.segments.filter(start_time__gt=after).order_by("start_time")
