"""Routes of the core app: the page and the JSON API."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/options/", views.OptionsView.as_view(), name="options"),
    path("api/jobs/", views.JobListView.as_view(), name="jobs"),
    path("api/jobs/<uuid:job_id>/", views.JobDetailView.as_view(), name="job"),
    path("api/jobs/<uuid:job_id>/cancel/", views.JobCancelView.as_view(), name="job-cancel"),
    path("api/jobs/<uuid:job_id>/retry/", views.JobRetryView.as_view(), name="job-retry"),
    path("api/jobs/<uuid:job_id>/segments/", views.JobSegmentsView.as_view(), name="job-segments"),
]
