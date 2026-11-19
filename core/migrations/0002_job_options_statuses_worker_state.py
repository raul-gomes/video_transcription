"""Per-job options, the full status lifecycle and the worker state row.

- `video_file` becomes `media_file` (audio is accepted too).
- New per-job choices: language, Whisper model and device.
- Status `pending` becomes `queued`; new statuses for model download,
  cancellation and interruption.
"""

from django.db import migrations, models

LEGACY_STATUS_MAP = {"pending": "queued"}


def migrate_legacy_statuses(apps, schema_editor):
    """Rename statuses that no longer exist."""
    job_model = apps.get_model("core", "TranscriptionJob")
    for old, new in LEGACY_STATUS_MAP.items():
        job_model.objects.filter(status=old).update(status=new)


def restore_legacy_statuses(apps, schema_editor):
    """Undo the status rename when migrating backwards."""
    job_model = apps.get_model("core", "TranscriptionJob")
    for old, new in LEGACY_STATUS_MAP.items():
        job_model.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="transcriptionjob",
            old_name="video_file",
            new_name="media_file",
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="original_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="media_kind",
            field=models.CharField(
                choices=[("video", "Vídeo"), ("audio", "Áudio")], default="video", max_length=10
            ),
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="language",
            field=models.CharField(default="pt", max_length=10),
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="model_name",
            field=models.CharField(default="small", max_length=20),
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="device",
            field=models.CharField(default="auto", max_length=10),
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="transcriptionjob",
            name="celery_task_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="transcriptionjob",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Na fila"),
                    ("downloading_model", "Baixando modelo…"),
                    ("extracting", "Extraindo áudio"),
                    ("transcribing", "Transcrevendo"),
                    ("generating", "Gerando legendas"),
                    ("completed", "Concluído"),
                    ("failed", "Falhou"),
                    ("cancelled", "Cancelado"),
                    ("interrupted", "Interrompido"),
                ],
                default="queued",
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_legacy_statuses, restore_legacy_statuses),
        migrations.CreateModel(
            name="WorkerState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("gpu_available", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
