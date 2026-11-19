"""Hand-written API payloads, matching static/js/contract.js."""

from django.db.models.fields.files import FieldFile
from rest_framework import serializers

from .constants import DEFAULT_LANGUAGE, DEVICE_AUTO
from .models import JobStatus, SubtitleSegment, TranscriptionJob

FILE_FIELDS = {
    "media": "media_file",
    "preview": "preview_file",
    "video": "final_video",
    "srt": "srt_file",
    "vtt": "vtt_file",
    "txt": "transcript_file",
    "json": "json_file",
}


def _url(stored: FieldFile) -> str | None:
    """Public URL of a stored file, or None when empty.

    Args:
        stored: A FileField value.

    Returns:
        The URL under MEDIA_URL, or None.
    """
    return stored.url if stored else None


class JobSerializer(serializers.ModelSerializer):
    """A Job as the history screen reads it."""

    filename = serializers.SerializerMethodField()
    progress = serializers.IntegerField(source="progress_percentage")
    step_label = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()
    model = serializers.CharField(source="model_name")
    files = serializers.SerializerMethodField()
    detected_language = serializers.SerializerMethodField()

    class Meta:
        model = TranscriptionJob
        fields = (
            "id",
            "filename",
            "media_kind",
            "status",
            "progress",
            "step_label",
            "error",
            "language",
            "detected_language",
            "model",
            "device",
            "created_at",
            "duration_seconds",
            "files",
            "analysis",
        )
        read_only_fields = fields

    def get_filename(self, job: TranscriptionJob) -> str:
        """Original file name, falling back to the stored one."""
        return job.original_filename or job.media_file.name.rsplit("/", 1)[-1]

    def get_step_label(self, job: TranscriptionJob) -> str:
        """Current step text, or the status label when there is none."""
        return job.current_step or JobStatus(job.status).label

    def get_error(self, job: TranscriptionJob) -> str | None:
        """Error message for failed jobs."""
        return job.error_message or None

    def get_detected_language(self, job: TranscriptionJob) -> str | None:
        """Language found in the first Bloco with speech (Automático only), or None."""
        return job.detected_language or None

    def get_files(self, job: TranscriptionJob) -> dict[str, str | None]:
        """URL of each downloadable file (None until it exists)."""
        return {key: _url(getattr(job, field)) for key, field in FILE_FIELDS.items()}


class SegmentSerializer(serializers.ModelSerializer):
    """A Segment for the live transcript."""

    start = serializers.FloatField(source="start_time")
    end = serializers.FloatField(source="end_time")

    class Meta:
        model = SubtitleSegment
        fields = ("start", "end", "text")
        read_only_fields = fields


class UploadSerializer(serializers.Serializer):
    """Upload form: the media file plus the per-job choices."""

    media = serializers.FileField(allow_empty_file=False)
    language = serializers.CharField(default=DEFAULT_LANGUAGE, max_length=10)
    model = serializers.CharField(required=False, max_length=20)
    device = serializers.CharField(default=DEVICE_AUTO, max_length=10)


class DecisionSerializer(serializers.Serializer):
    """Body of POST /api/jobs/<id>/confirm/ (the Análise da Mídia modal)."""

    audio_track = serializers.IntegerField(min_value=0)
    language = serializers.CharField(max_length=10)
    model = serializers.CharField(max_length=20)
    device = serializers.CharField(max_length=10)
    preview = serializers.BooleanField()
    convert_video = serializers.BooleanField()
