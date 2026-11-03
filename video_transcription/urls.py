"""
URL configuration for video_transcription project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls', namespace='core')),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from core.views import serve_media
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Mídia servida por uma view própria, com suporte a HTTP Range (seek em vídeos).
    urlpatterns += [path('media/<path:path>', serve_media, name='serve_media')]
