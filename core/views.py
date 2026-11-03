import mimetypes
import os
import re
from django.conf import settings
from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse, FileResponse, Http404, StreamingHttpResponse, HttpResponse
from .models import TranscriptionJob, LANGUAGE_CHOICES, LANGUAGE_LABELS
from .tasks import process_video_task


def _fmt_duration(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def _status_label(job):
    """Rótulo em português para o status do job."""
    return {
        'pending': 'Na fila',
        'extracting': 'Extraindo o áudio',
        'transcribing': 'Transcrevendo',
        'generating': 'Gerando legendas',
        'completed': 'Concluído',
        'failed': 'Falhou',
    }.get(job.status, job.status)


def _language_label(code):
    """Rótulo em português para um código de idioma do Whisper."""
    code = (code or '').strip().lower()
    if not code:
        return ''
    return LANGUAGE_LABELS.get(code, code.upper())


def _job_summary(job):
    """Resumo de um job usado na listagem da biblioteca."""
    return {
        'id': str(job.id),
        'name': os.path.basename(job.video_file.name) if job.video_file else '—',
        'status': job.status,
        'status_label': _status_label(job),
        'progress': job.progress_percentage,
        'current_step': 'Transcrição concluída!' if job.status == 'completed' else job.current_step,
        'duration': job.duration_seconds or 0,
        'duration_label': _fmt_duration(job.duration_seconds),
        'segments': job.segments.count(),
        'language': job.language or '',
        'language_label': _language_label(job.language),
        'created_at': job.created_at.isoformat(),
        'created_label': timezone.localtime(job.created_at).strftime('%d/%m/%Y %H:%M'),
        'has_final': bool(job.final_video),
        'active': job.status not in ('completed', 'failed'),
    }


class IndexView(APIView):
    def get(self, request):
        return render(request, 'core/index.html')


class LibraryView(APIView):
    """Página com todos os vídeos enviados e o progresso de cada um."""

    def get(self, request):
        jobs = [_job_summary(j) for j in TranscriptionJob.objects.all()]
        return render(request, 'core/library.html', {'jobs': jobs})


class VideoDetailView(APIView):
    """Página do player de um vídeo específico."""

    def get(self, request, job_id):
        try:
            job = TranscriptionJob.objects.get(id=job_id)
        except TranscriptionJob.DoesNotExist:
            raise Http404('Job not found')
        return render(request, 'core/detail.html', {'job': job})


class JobListView(APIView):
    """API com a lista de jobs (usada para atualizar a biblioteca em tempo real)."""

    def get(self, request):
        return Response([_job_summary(j) for j in TranscriptionJob.objects.all()])


class UploadVideoView(APIView):
    def post(self, request):
        video_file = request.FILES.get('video_file')

        if not video_file:
            return Response({'error': 'No video file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Idioma escolhido pelo usuário. Vazio (ou inválido) = detectar sozinho.
        language = (request.data.get('language') or '').strip().lower()
        allowed = {code for code, _ in LANGUAGE_CHOICES if code}
        if language not in allowed:
            language = ''

        job = TranscriptionJob.objects.create(
            video_file=video_file,
            status='pending',
            language=language,
        )

        process_video_task.delay(str(job.id))

        return Response({
            'job_id': str(job.id),
            'status': 'Uploaded',
            'language': language,
            'video_url': job.video_file.url if job.video_file else None,
            'message': 'Video uploaded successfully. Processing started.'
        })


class JobProgressView(APIView):
    def get(self, request, job_id):
        try:
            job = TranscriptionJob.objects.get(id=job_id)
            files = {
                'srt': job.srt_file.url if job.srt_file else None,
                'vtt': job.vtt_file.url if job.vtt_file else None,
                'transcript': job.transcript_file.url if job.transcript_file else None,
                'video': job.final_video.url if job.final_video else None,
            }
            segments = [
                {
                    'start': seg.start_time,
                    'end': seg.end_time,
                    'text': seg.text,
                }
                for seg in job.segments.all()
            ]
            return Response({
                'job_id': str(job.id),
                'status': job.status,
                'status_label': _status_label(job),
                'progress_percentage': job.progress_percentage,
                'current_step': job.current_step,
                'duration_seconds': job.duration_seconds,
                'language': job.language or '',
                'language_label': _language_label(job.language),
                'segments_count': len(segments),
                'segments': segments,
                # Vídeo original enviado pelo usuário (usado para reproduzir).
                'video_url': job.video_file.url if job.video_file else None,
                'files': files,
                'file': files,
            })
        except TranscriptionJob.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class _DownloadMixin:
    """Base view that streams a file field from a TranscriptionJob."""

    field_name = None
    download_name = None

    def get(self, request, job_id):
        try:
            job = TranscriptionJob.objects.get(id=job_id)
        except TranscriptionJob.DoesNotExist:
            raise Http404('Job not found')

        file_field = getattr(job, self.field_name, None)
        if not file_field or not file_field.name:
            raise Http404('File not available for this job')

        try:
            handle = file_field.open('rb')
        except FileNotFoundError:
            raise Http404('File not found on disk')

        content_type, _ = mimetypes.guess_type(file_field.name)
        response = FileResponse(handle, content_type=content_type or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{self.download_name}"'
        return response


class DownloadVideoView(_DownloadMixin, APIView):
    field_name = 'final_video'
    download_name = 'video_com_legendas.mp4'


class DownloadSrtView(_DownloadMixin, APIView):
    field_name = 'srt_file'
    download_name = 'legendas.srt'


class DownloadVttView(_DownloadMixin, APIView):
    field_name = 'vtt_file'
    download_name = 'legendas.vtt'


class DownloadTranscriptView(_DownloadMixin, APIView):
    field_name = 'transcript_file'
    download_name = 'transcricao.txt'


# --------------------------------------------------------------------------
# Servidor de mídia com suporte a HTTP Range.
#
# O `django.views.static.serve` (usado em desenvolvimento) não implementa
# "Range requests", o que impede o navegador de avançar/retroceder em vídeos
# grandes (o seek "volta para o início"). Esta view responde 206 Partial
# Content e habilita o seek.
# --------------------------------------------------------------------------
_RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)')


def _iter_file(path, start, length, chunk_size=64 * 1024):
    with open(path, 'rb') as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            data = handle.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def serve_media(request, path):
    media_root = os.path.realpath(str(settings.MEDIA_ROOT))
    full_path = os.path.realpath(os.path.join(media_root, path))
    if not (full_path == media_root or full_path.startswith(media_root + os.sep)) or not os.path.isfile(full_path):
        raise Http404('Media not found')

    size = os.path.getsize(full_path)
    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or 'application/octet-stream'

    range_header = request.headers.get('Range')
    if range_header:
        match = _RANGE_RE.fullmatch(range_header.strip())
        if match:
            start = int(match.group(1)) if match.group(1) else 0
            end = int(match.group(2)) if match.group(2) else size - 1
            if start >= size or start > end:
                response = HttpResponse(status=416)
                response['Content-Range'] = f'bytes */{size}'
                return response
            end = min(end, size - 1)
            length = end - start + 1
            response = StreamingHttpResponse(
                _iter_file(full_path, start, length),
                status=206,
                content_type=content_type,
            )
            response['Content-Length'] = str(length)
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
            response['Accept-Ranges'] = 'bytes'
            return response

    response = FileResponse(open(full_path, 'rb'), content_type=content_type)
    response['Content-Length'] = str(size)
    response['Accept-Ranges'] = 'bytes'
    return response

