"""
Management command to load ArtworkStats table from Qdrant collection.

Uses Qdrant as the source of truth for artwork statistics.
Performs atomic updates using database transactions to avoid downtime.

Usage:
    python manage.py load_artwork_stats [--drop-existing]
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from artsearch.models import ArtworkStats
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.config import config
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load ArtworkStats table from Qdrant collection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop-existing",
            action="store_true",
            help="Drop all existing ArtworkStats records before loading",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Batch size for fetching from Qdrant (default: 2000)",
        )
        parser.add_argument(
            "--bulk-create-batch",
            type=int,
            default=1000,
            help="Batch size for bulk_create operations (default: 1000)",
        )

    def handle(self, *args, **options):
        drop_existing = options["drop_existing"]
        batch_size = options["batch_size"]
        bulk_create_batch = options["bulk_create_batch"]

        self.stdout.write(self.style.SUCCESS("Starting ArtworkStats load..."))

        # Get Qdrant service
        collection_name = config.qdrant_collection_name_app
        qdrant_service = QdrantService(collection_name=collection_name)

        # Step 1: Fetch all artwork data from Qdrant
        self.stdout.write(
            f"Fetching artworks from Qdrant collection: {collection_name}"
        )
        artwork_records = self._fetch_artworks_from_qdrant(
            qdrant_service, collection_name, batch_size
        )

        if not artwork_records:
            self.stdout.write(self.style.WARNING("No artworks found in Qdrant"))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Fetched {len(artwork_records)} artworks from Qdrant")
        )

        # Step 2: Perform atomic database update
        self.stdout.write("Updating database...")
        self._update_database(artwork_records, drop_existing, bulk_create_batch)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully loaded ArtworkStats with {len(artwork_records)} records"
            )
        )

    def _fetch_artworks_from_qdrant(
        self, qdrant_service, collection_name: str, batch_size: int
    ) -> list[dict]:
        """
        Fetch all artworks from Qdrant collection.
        Returns list of dicts with museum, object_number, searchable_work_types.
        """
        artwork_records = []
        next_page_token = None
        processed_count = 0

        while True:
            points, next_page_token = qdrant_service.fetch_points(
                next_page_token,
                limit=batch_size,
                with_payload=["museum", "object_number", "searchable_work_types"],
            )

            for point in points:
                payload = point.payload
                if payload is None:
                    logger.warning(f"Skipping point {point.id} with missing payload")
                    continue

                museum = payload.get("museum")
                object_number = payload.get("object_number")
                searchable_work_types = payload.get("searchable_work_types", [])

                # Validation
                if not museum:
                    logger.warning(f"Skipping point {point.id} with missing museum")
                    continue
                if not object_number:
                    logger.warning(
                        f"Skipping point {point.id} with missing object_number"
                    )
                    continue
                if not isinstance(searchable_work_types, list):
                    logger.warning(
                        f"Skipping point {point.id} with invalid searchable_work_types"
                    )
                    continue

                artwork_records.append(
                    {
                        "museum_slug": museum,
                        "object_number": object_number,
                        "searchable_work_types": searchable_work_types,
                    }
                )

            processed_count += len(points)
            self.stdout.write(f"  Processed {processed_count} points...", ending="\r")

            if next_page_token is None:
                break

        self.stdout.write("")  # New line after progress
        return artwork_records

    def _update_database(
        self, artwork_records: list[dict], drop_existing: bool, bulk_create_batch: int
    ):
        """
        Update database with artwork records.
        Uses transaction for atomicity to avoid downtime.
        """
        with transaction.atomic():
            if drop_existing:
                self.stdout.write("  Dropping existing ArtworkStats records...")
                deleted_count, _ = ArtworkStats.objects.all().delete()
                self.stdout.write(f"  Deleted {deleted_count} existing records")

            # Bulk create in batches
            self.stdout.write(
                f"  Creating {len(artwork_records)} ArtworkStats records..."
            )

            # Convert to ArtworkStats objects
            artwork_stats_objects = [
                ArtworkStats(
                    museum_slug=record["museum_slug"],
                    object_number=record["object_number"],
                    searchable_work_types=record["searchable_work_types"],
                )
                for record in artwork_records
            ]

            # Bulk create in batches for memory efficiency
            created_count = 0
            for i in range(0, len(artwork_stats_objects), bulk_create_batch):
                batch = artwork_stats_objects[i : i + bulk_create_batch]
                ArtworkStats.objects.bulk_create(
                    batch,
                    ignore_conflicts=True,  # Skip duplicates (shouldn't happen but safe)
                )
                created_count += len(batch)
                self.stdout.write(
                    f"  Created {created_count}/{len(artwork_stats_objects)} records...",
                    ending="\r",
                )

            self.stdout.write("")  # New line after progress
            self.stdout.write(
                self.style.SUCCESS(f"  Created {created_count} ArtworkStats records")
            )
