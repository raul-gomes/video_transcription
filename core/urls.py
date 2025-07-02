from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('api/upload/', views.UploadVideoView.as_view(), name='upload'),
    path('api/progress/<uuid:job_id>', views.JobProgressView.as_view(), name='progress'),
]