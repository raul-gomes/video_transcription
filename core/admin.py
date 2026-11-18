from django.contrib import admin

from .models import SubtitleSegment, TranscriptionJob


# Register your models here.
@admin.register(TranscriptionJob)
class TranscriptionJobAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "progress_percentage", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(SubtitleSegment)
class SubtitleSegmentAdmin(admin.ModelAdmin):
    list_display = ["job", "start_time", "end_time", "text"]
    list_filter = ["job__status"]
