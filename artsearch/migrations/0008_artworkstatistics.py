# Generated migration for ArtworkStatistics model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('artsearch', '0007_delete_metadataraw'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArtworkStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('museum', models.CharField(help_text="Museum slug (e.g., 'smk', 'met', 'cma', 'rma')", max_length=10)),
                ('work_type', models.CharField(blank=True, help_text='Work type name (null for total count)', max_length=100, null=True)),
                ('count', models.IntegerField(default=0, help_text='Number of artworks for this museum/work_type combination')),
                ('last_updated', models.DateTimeField(auto_now=True, help_text='When these stats were last computed')),
            ],
        ),
        migrations.AddConstraint(
            model_name='artworkstatistics',
            constraint=models.UniqueConstraint(fields=['museum', 'work_type'], name='uniq_stats_museum_work_type'),
        ),
        migrations.AddIndex(
            model_name='artworkstatistics',
            index=models.Index(fields=['museum'], name='artsearch_a_museum_idx'),
        ),
        migrations.AddIndex(
            model_name='artworkstatistics',
            index=models.Index(fields=['work_type'], name='artsearch_a_work_ty_idx'),
        ),
    ]
