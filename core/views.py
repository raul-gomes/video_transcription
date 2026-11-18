from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TranscriptionJob
from .tasks import process_video_task


# Create your views here.
class IndexView(APIView):
    """
    View to render the index page.
    """

    def get(self, request):
        return render(request, "core/index.html")


class UploadVideoView(APIView):
    """
    View to handle video file uploads.
    """

    def post(self, request):
        video_file = request.FILES.get("video_file")

        if not video_file:
            return Response({"error": "No video file provided"}, status=status.HTTP_400_BAD_REQUEST)

        job = TranscriptionJob.objects.create(
            video_file=video_file,
            status="pending",
        )

        process_video_task.delay(str(job.id))

        return Response(
            {
                "job_id": str(job.id),
                "status": "Uploaded",
                "message": "Video uploaded successfully. Processing started.",
            }
        )


class JobProgressView(APIView):
    """
    View to check the progress of a transcription job.
    """

    def get(self, request, job_id):
        try:
            job = TranscriptionJob.objects.get(id=job_id)
            return Response(
                {
                    "job_id": str(job.id),
                    "status": job.status,
                    "progress_percentage": job.progress_percentage,
                    "current_step": job.current_step,
                    "file": {
                        "srt": job.srt_file.url if job.srt_file else None,
                        "vtt": job.vtt_file.url if job.vtt_file else None,
                        "transcript": job.transcript_file.url if job.transcript_file else None,
                        "video": job.final_video.url if job.final_video else None,
                    },
                }
            )
        except TranscriptionJob.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
