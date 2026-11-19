import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "video_transcription.settings")

app = Celery("video_transcription")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
