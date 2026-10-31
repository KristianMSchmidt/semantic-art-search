"""
Score how colourful each artwork's thumbnail is (ArtworkStats.colorfulness).

Only scores rows without a score, so run it after load_artwork_stats to
score newly loaded artworks. `--force` rescores everything. Artworks whose
thumbnail can't be fetched stay unscored and are retried on the next run.

Usage:
    python manage.py compute_colorfulness [--force] [--limit N] [--workers N]
"""

from django.core.management.base import BaseCommand

from artsearch.models import ArtworkStats
from etl.services.colorfulness_service import score_artworks


class Command(BaseCommand):
    help = "Score the colourfulness of artwork thumbnails (ArtworkStats)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Rescore artworks already scored"
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Score at most N artworks"
        )
        parser.add_argument(
            "--workers", type=int, default=16, help="Parallel downloads (default 16)"
        )
        parser.add_argument(
            "--batch-size", type=int, default=500, help="Rows saved per batch"
        )

    def handle(self, *args, **options):
        queryset = ArtworkStats.objects.order_by("id")
        if not options["force"]:
            queryset = queryset.filter(colorfulness__isnull=True)
        # Fix the work list up front, so failures (left null) aren't retried
        # within this run
        ids = list(queryset.values_list("id", flat=True)[: options["limit"]])
        self.stdout.write(f"Scoring {len(ids)} artworks...")

        batch_size = options["batch_size"]
        scored = failed = 0
        for start in range(0, len(ids), batch_size):
            rows = list(
                ArtworkStats.objects.filter(id__in=ids[start : start + batch_size])
            )
            scores = score_artworks(
                [(row.museum_slug, row.object_number) for row in rows],
                workers=options["workers"],
            )
            to_update = []
            for row, score in zip(rows, scores):
                if score is None:
                    failed += 1
                    continue
                row.colorfulness = score
                to_update.append(row)
            ArtworkStats.objects.bulk_update(to_update, ["colorfulness"])
            scored += len(to_update)
            self.stdout.write(
                f"  {scored + failed}/{len(ids)} done ({failed} failed)", ending="\r"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Scored {scored} artworks, {failed} failed")
        )
