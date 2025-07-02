# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery (em outro terminal)
celery -A video_transcription worker -l info

# Terminal 3: Redis (se necessário)
redis-server