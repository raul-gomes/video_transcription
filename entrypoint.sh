#!/bin/bash
set -e

echo ">>> Aguardando dependencias..."
python /app/wait_for_services.py

case "$1" in
  web)
    echo ">>> Aplicando migracoes..."
    python manage.py migrate --noinput
    echo ">>> Coletando arquivos estaticos..."
    python manage.py collectstatic --noinput --clear >/dev/null 2>&1 || true
    echo ">>> Iniciando servico: web"
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  worker)
    echo ">>> Iniciando servico: worker"
    exec celery -A video_transcription worker -l info
    ;;
  beat)
    echo ">>> Iniciando servico: beat"
    exec celery -A video_transcription beat -l info
    ;;
  *)
    exec "$@"
    ;;
esac
