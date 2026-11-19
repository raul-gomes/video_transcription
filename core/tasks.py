"""Celery tasks."""

from celery import shared_task
from loguru import logger

from .models import JobStatus, TranscriptionJob
from .utils import VideoProcessor


@shared_task
def process_video_task(job_id: str) -> None:
    """Run the transcription pipeline for one job.

    Any error is recorded on the job itself, so the page can show it; the
    result backend is never the only place an error lands.

    Args:
        job_id: Primary key of the TranscriptionJob to process.
    """
    try:
        job = TranscriptionJob.objects.get(id=job_id)
    except TranscriptionJob.DoesNotExist:
        logger.warning(f"[{job_id}] Job not found; it may have been deleted.")
        return
    if job.status != JobStatus.QUEUED:
        logger.info(f"[{job_id}] Skipped: status is {job.status}, not queued.")
        return

    try:
        VideoProcessor(job).process()
    except Exception as error:
        logger.exception(f"[{job_id}] Unexpected error while processing.")
        TranscriptionJob.objects.filter(pk=job.pk).update(
            status=JobStatus.FAILED, error_message=f"Erro inesperado: {error}"
        )
