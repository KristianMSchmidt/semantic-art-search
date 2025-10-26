# Generated migration for ArtworkWorkTypeMapping model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('artsearch', '0008_artworkstatistics'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArtworkWorkTypeMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qdrant_id', models.BigIntegerField(help_text='Qdrant point ID for the artwork')),
                ('museum', models.CharField(help_text='Museum slug', max_length=10)),
                ('object_number', models.CharField(help_text='Unique artwork identifier', max_length=100)),
                ('work_types', models.JSONField(default=list, help_text='List of searchable work types for this artwork')),
                ('last_updated', models.DateTimeField(auto_now=True, help_text='When this mapping was last computed')),
            ],
        ),
        migrations.AddConstraint(
            model_name='artworkworktypemapping',
            constraint=models.UniqueConstraint(fields=['qdrant_id'], name='uniq_mapping_qdrant_id'),
        ),
        migrations.AddIndex(
            model_name='artworkworktypemapping',
            index=models.Index(fields=['museum'], name='artsearch_m_museum_idx'),
        ),
        migrations.AddIndex(
            model_name='artworkworktypemapping',
            index=models.Index(fields=['object_number'], name='artsearch_m_object__idx'),
        ),
    ]
