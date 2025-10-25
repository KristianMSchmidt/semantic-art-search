# Migration to fix qdrant_id field type from BigIntegerField to CharField

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('artsearch', '0009_artworkworktypemapping'),
    ]

    operations = [
        migrations.AlterField(
            model_name='artworkworktypemapping',
            name='qdrant_id',
            field=models.CharField(help_text='Qdrant point ID for the artwork (UUID)', max_length=100),
        ),
    ]
