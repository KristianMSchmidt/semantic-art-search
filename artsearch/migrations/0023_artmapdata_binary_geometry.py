from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('artsearch', '0022_artmapdata'),
    ]

    operations = [
        migrations.RenameField(
            model_name='artmapdata',
            old_name='data',
            new_name='metadata',
        ),
        migrations.AlterField(
            model_name='artmapdata',
            name='metadata',
            field=models.TextField(help_text='JSON string of metadata (titles, artists, etc.)'),
        ),
        migrations.AddField(
            model_name='artmapdata',
            name='geometry',
            field=models.BinaryField(blank=True, help_text='Packed binary geometry data', null=True),
        ),
    ]
