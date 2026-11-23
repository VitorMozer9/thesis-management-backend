import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('thesis', '0003_thesis_audit'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdfExtractionModel',
            fields=[
                ('thesis', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='thesis.thesismodel')),
                ('event_id', models.UUIDField(unique=True)),
                ('file_key', models.CharField(max_length=512)),
                ('file_sha256', models.CharField(max_length=64)),
                ('status', models.CharField(choices=[('pending', 'PENDING'), ('processing', 'PROCESSING'), ('completed', 'COMPLETED'), ('failed', 'FAILED')], default='pending', max_length=16)),
                ('text', models.TextField(blank=True, default='')),
                ('finished_at', models.DateTimeField(null=True)),
                ('failure_code', models.CharField(blank=True, default='', max_length=32)),
            ],
            options={
                'db_table': 'thesis_pdf_extractions',
            },
        ),
        migrations.RunSQL(
            """
            INSERT INTO thesis_pdf_extractions
                (thesis_id, event_id, file_key, file_sha256, status, text, failure_code)
            SELECT t.id, e.id, t.file_key, t.file_sha256, 'pending', '', ''
            FROM theses t
            JOIN outbox_events e ON e.aggregate_id = t.id
            WHERE e.event_type = 'thesis.submitted'
              AND t.status <> 'draft'
              AND t.file_key IS NOT NULL AND t.file_sha256 IS NOT NULL
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
