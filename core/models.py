from django.db import models
import uuid


# Idiomas oferecidos no seletor de upload. Vazio = detectar automaticamente
# (o Whisper identifica o idioma do áudio sozinho).
LANGUAGE_CHOICES = [
    ('', 'Detectar automaticamente'),
    ('pt', 'Português'),
    ('en', 'Inglês'),
    ('es', 'Espanhol'),
    ('fr', 'Francês'),
    ('de', 'Alemão'),
    ('it', 'Italiano'),
    ('ja', 'Japonês'),
    ('zh', 'Chinês'),
    ('ru', 'Russo'),
]

LANGUAGE_LABELS = dict(LANGUAGE_CHOICES)


class TranscriptionJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('extracting', 'Extracting'),
        ('transcribing', 'Transcribing'),
        ('generating', 'Generating subtitles'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.FileField(upload_to='videos/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, blank=True)

    audio_file = models.FileField(upload_to='audio/', blank=True)
    srt_file = models.FileField(upload_to='subtitles/', blank=True)
    vtt_file = models.FileField(upload_to='subtitles/', blank=True)
    json_file = models.FileField(upload_to='subtitles/', blank=True)
    transcript_file = models.FileField(upload_to='transcripts/', blank=True)
    final_video = models.FileField(upload_to='processed/', blank=True)

    duration_seconds = models.FloatField(null=True, blank=True)
    # Idioma escolhido pelo usuário ('' = automático) e, depois, o idioma
    # efetivamente usado/detectado na transcrição.
    language = models.CharField(max_length=10, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Job {self.id} - {self.video_file.name} - {self.status}'


class SubtitleSegment(models.Model):
    job = models.ForeignKey(TranscriptionJob, on_delete=models.CASCADE, related_name='segments')
    start_time = models.FloatField()
    end_time = models.FloatField()
    text = models.TextField()
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f'Segment {self.start_time:.1f}s'
