from django.db import models
import uuid

# Create your models here.
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

    # Arquivos gerados
    audio_file = models.FileField(upload_to='audio/', blank=True)
    srt_file = models.FileField(upload_to='subtitles/', blank=True)
    vtt_file = models.FileField(upload_to='subtitles/', blank=True)
    json_file = models.FileField(upload_to='subtitles/', blank=True)
    transcript_file = models.FileField(upload_to='transcripts/', blank=True)
    final_video = models.FileField(upload_to='processed/', blank=True)

    # Metadata
    duration_seconds = models.FloatField(null=True, blank=True)
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
