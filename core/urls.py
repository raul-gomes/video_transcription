from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('videos/', views.LibraryView.as_view(), name='library'),
    path('videos/<uuid:job_id>/', views.VideoDetailView.as_view(), name='detail'),
    path('api/upload/', views.UploadVideoView.as_view(), name='upload'),
    path('api/jobs/', views.JobListView.as_view(), name='jobs'),
    path('api/progress/<uuid:job_id>/', views.JobProgressView.as_view(), name='progress'),
    path('api/transcription/<uuid:job_id>/download_video/', views.DownloadVideoView.as_view(), name='download_video'),
    path('api/transcription/<uuid:job_id>/download_srt/', views.DownloadSrtView.as_view(), name='download_srt'),
    path('api/transcription/<uuid:job_id>/download_vtt/', views.DownloadVttView.as_view(), name='download_vtt'),
    path('api/transcription/<uuid:job_id>/download_transcript/', views.DownloadTranscriptView.as_view(), name='download_transcript'),
]
