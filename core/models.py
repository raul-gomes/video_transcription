"""Database models: Job (TranscriptionJob), Segment (SubtitleSegment) and worker state."""

import uuid

from django.db import models

from .constants import DEFAULT_LANGUAGE, DEVICE_AUTO


class JobStatus(models.TextChoices):
    """Lifecycle of a Job. Labels are the pt-BR text shown on the page."""

    AWAITING_DECISION = "awaiting_decision", "Aguardando sua decisão"
    QUEUED = "queued", "Na fila"
    PREPARING_PREVIEW = "preparing_preview", "Preparando prévia"
    DOWNLOADING_MODEL = "downloading_model", "Baixando modelo…"
    EXTRACTING = "extracting", "Extraindo áudio"
    TRANSCRIBING = "transcribing", "Transcrevendo"
    GENERATING = "generating", "Gerando legendas"
    COMPLETED = "completed", "Concluído"
    FAILED = "failed", "Falhou"
    CANCELLED = "cancelled", "Cancelado"
    INTERRUPTED = "interrupted", "Interrompido"


#: Statuses where a job is waiting or running and can be cancelled.
ACTIVE_STATUSES = frozenset(
    {
        JobStatus.QUEUED,
        JobStatus.PREPARING_PREVIEW,
        JobStatus.DOWNLOADING_MODEL,
        JobStatus.EXTRACTING,
        JobStatus.TRANSCRIBING,
        JobStatus.GENERATING,
    }
)
#: Statuses where a worker is processing the job right now.
RUNNING_STATUSES = ACTIVE_STATUSES - {JobStatus.QUEUED}
#: Statuses that can be sent back to the queue.
RETRYABLE_STATUSES = frozenset({JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.INTERRUPTED})


class MediaKind(models.TextChoices):
    """Whether the uploaded media is a video or audio only."""

    VIDEO = "video", "Vídeo"
    AUDIO = "audio", "Áudio"


class TranscriptionJob(models.Model):
    """A Job: one media file being transcribed, from upload to the end."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media_file = models.FileField(upload_to="videos/")
    original_filename = models.CharField(max_length=255, blank=True)
    media_kind = models.CharField(max_length=10, choices=MediaKind.choices, default=MediaKind.VIDEO)
    language = models.CharField(max_length=10, default=DEFAULT_LANGUAGE)
    #: In Automático, the language Whisper found in the first Bloco with speech (ADR 0003).
    detected_language = models.CharField(max_length=10, blank=True)
    model_name = models.CharField(max_length=20, default="small")
    device = models.CharField(max_length=10, default=DEVICE_AUTO)

    status = models.CharField(
        max_length=20, choices=JobStatus.choices, default=JobStatus.AWAITING_DECISION
    )
    progress_percentage = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=64, blank=True)

    # Análise da Mídia and the person's decision (ADR 0007)
    analysis = models.JSONField(null=True, blank=True)
    audio_stream_index = models.IntegerField(null=True, blank=True)
    make_preview = models.BooleanField(default=False)
    convert_video = models.BooleanField(default=False)
    preview_file = models.FileField(upload_to="previews/", blank=True)

    # Generated files
    audio_file = models.FileField(upload_to="audio/", blank=True)
    srt_file = models.FileField(upload_to="subtitles/", blank=True)
    vtt_file = models.FileField(upload_to="subtitles/", blank=True)
    json_file = models.FileField(upload_to="subtitles/", blank=True)
    transcript_file = models.FileField(upload_to="transcripts/", blank=True)
    final_video = models.FileField(upload_to="processed/", blank=True)

    duration_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Readable identifier for logs and the admin."""
        return f"Job {self.id} - {self.original_filename or self.media_file.name} - {self.status}"

    @property
    def is_active(self) -> bool:
        """True while the job waits in the queue or is being processed."""
        return self.status in ACTIVE_STATUSES


class SubtitleSegment(models.Model):
    """A Segment: one timed sentence of the transcript (source of truth for subtitles)."""

    job = models.ForeignKey(TranscriptionJob, on_delete=models.CASCADE, related_name="segments")
    start_time = models.FloatField()
    end_time = models.FloatField()
    text = models.TextField()
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self) -> str:
        """Readable identifier for logs and the admin."""
        return f"Segment {self.start_time:.1f}s"


class WorkerState(models.Model):
    """What the transcription worker reported when it started (single row)."""

    SINGLETON_ID = 1

    gpu_available = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Readable identifier for logs and the admin."""
        return f"Worker (GPU: {self.gpu_available})"

    @classmethod
    def current(cls) -> "WorkerState":
        """Return the single worker state row, empty until a worker starts."""
        state, _ = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        return state
