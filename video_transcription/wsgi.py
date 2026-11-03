"""
WSGI config for video_transcription project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'video_transcription.settings')

application = get_wsgi_application()
