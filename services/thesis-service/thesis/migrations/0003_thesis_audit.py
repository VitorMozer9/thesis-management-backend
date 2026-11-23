import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('thesis', '0002_outboxeventmodel'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThesisAuditModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('account_id', models.UUIDField()),
                ('academic_id', models.UUIDField()),
                ('role', models.CharField(max_length=16)),
                ('action', models.CharField(max_length=32)),
                ('thesis_id', models.UUIDField(db_index=True)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'thesis_audit',
                'default_permissions': (),
            },
        ),
    ]
