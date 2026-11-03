import artsearch.models
from django.db import migrations, models

HELP_TEXT = (
    "Fixed random position in [0, 1) for browsing in random order: a seed "
    "picks a start point and pages read on from there, which an index makes "
    "cheap (see browse_service)"
)


class Migration(migrations.Migration):
    """
    Add ArtworkStats.random_key. A plain AddField would evaluate the default
    once and give every existing row the same key, so add it nullable, give
    each row its own random() value, then make it required.
    """

    dependencies = [
        ("artsearch", "0031_map_search_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="artworkstats",
            name="random_key",
            field=models.FloatField(null=True, help_text=HELP_TEXT),
        ),
        migrations.RunSQL(
            "UPDATE artsearch_artworkstats SET random_key = random()",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="artworkstats",
            name="random_key",
            field=models.FloatField(
                default=artsearch.models.new_random_key, help_text=HELP_TEXT
            ),
        ),
        migrations.AddIndex(
            model_name="artworkstats",
            index=models.Index(
                fields=["random_key", "id"], name="artsearch_a_random__bb8237_idx"
            ),
        ),
    ]
