from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from artsearch.models import ImageSearchLog
from artsearch.src.services.image_upload_service import DAILY_EMBEDDING_CAP

STATUSES = [status for status, _ in ImageSearchLog.Status.choices]


class Command(BaseCommand):
    help = "Show image search uploads per day (UTC), by status"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30, help="Number of most recent days to show"
        )

    def handle(self, *args, **options):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        since = today - timedelta(days=options["days"] - 1)
        rows = (
            ImageSearchLog.objects.filter(timestamp__gte=since)
            .annotate(day=TruncDate("timestamp"))
            .values("day", "status")
            .annotate(count=Count("id"))
        )
        counts: dict = {}
        for row in rows:
            counts.setdefault(row["day"], {})[row["status"]] = row["count"]

        days = sorted(counts, reverse=True)
        if not days:
            self.stdout.write("No image searches yet.")
            return

        header = f"{'date':<12}" + "".join(f"{s:>11}" for s in STATUSES) + f"{'total':>8}"
        self.stdout.write(
            f"Daily cap: {DAILY_EMBEDDING_CAP} Jina calls (embedded + failed)"
        )
        self.stdout.write(header)
        for day in days:
            per_status = counts[day]
            self.stdout.write(
                f"{day.isoformat():<12}"
                + "".join(f"{per_status.get(s, 0):>11}" for s in STATUSES)
                + f"{sum(per_status.values()):>8}"
            )
