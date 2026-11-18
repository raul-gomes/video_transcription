from celery import shared_task

from .models import TranscriptionJob
from .utils import VideoProcessor


@shared_task(bind=True)
def process_video_task(self, job_id):
    """
    Task to process a video transcription job.
    """
    try:
        job = TranscriptionJob.objects.get(id=job_id)
        processor = VideoProcessor(job)

        processor.process()

    except TranscriptionJob.DoesNotExist:
        self.update_state(state="FAILURE", meta={"error": "Job not found"})
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
