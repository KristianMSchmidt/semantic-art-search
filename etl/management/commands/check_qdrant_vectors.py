"""
Management command to sanity check the vectors in a Qdrant collection.

Samples points per museum and reports how many have zero-norm vectors
for each named vector. Zero vectors score 0 on every query, so a
collection where e.g. `image_jina` is all zeros gives meaningless search
results (see `make sync-qdrant-local` for refreshing the dev collection).

Usage:
    python manage.py check_qdrant_vectors [--sample-size 50]
"""

from django.core.management.base import BaseCommand
from qdrant_client import models
from artsearch.src.config import config
from artsearch.src.constants.search_modes import SEARCH_MODE_TO_VECTOR_NAME
from artsearch.src.utils.get_museums import get_museum_slugs
from artsearch.src.utils.get_qdrant_client import get_qdrant_client

# Vectors used for search. Other vectors (e.g. the deprecated CLIP ones) are
# expected to be zero and are reported for information only.
SEARCH_VECTOR_NAMES = set(SEARCH_MODE_TO_VECTOR_NAME.values())


def is_zero_vector(vector: list[float]) -> bool:
    return not any(vector)


def count_zero_vectors(
    point_vectors: list[dict[str, list[float]]],
) -> dict[str, int]:
    """Count zero-norm vectors per vector name."""
    counts: dict[str, int] = {}
    for vectors in point_vectors:
        for name, vector in vectors.items():
            counts[name] = counts.get(name, 0) + is_zero_vector(vector)
    return counts


class Command(BaseCommand):
    help = "Report zero-norm vectors per museum in the app's Qdrant collection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-size",
            type=int,
            default=50,
            help="Number of points to sample per museum (default: 50)",
        )

    def handle(self, *args, **options):
        sample_size = options["sample_size"]
        collection_name = config.qdrant_collection_name_app
        client = get_qdrant_client()

        points_count = client.get_collection(collection_name).points_count
        self.stdout.write(f"Collection: {collection_name} ({points_count:,} points)")
        self.stdout.write(f"Sampling up to {sample_size} points per museum\n")

        problems = []
        for museum in get_museum_slugs():
            points, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="museum", match=models.MatchValue(value=museum)
                        )
                    ]
                ),
                limit=sample_size,
                with_vectors=True,
            )
            if not points:
                self.stdout.write(f"  {museum}: no points")
                continue

            zero_counts = count_zero_vectors([p.vector for p in points])  # type: ignore[misc]
            summary = ", ".join(
                f"{name}={zero_counts[name]}" for name in sorted(zero_counts)
            )
            self.stdout.write(f"  {museum} ({len(points)} sampled) zero vectors: {summary}")

            for name in SEARCH_VECTOR_NAMES:
                if zero_counts.get(name, 0) > 0:
                    problems.append(f"{museum}: {zero_counts[name]} zero {name} vectors")

        self.stdout.write("")
        if problems:
            self.stdout.write(
                self.style.WARNING(
                    "Zero-norm search vectors found (search results will be skewed):"
                )
            )
            for problem in problems:
                self.stdout.write(self.style.WARNING(f"  {problem}"))
            self.stdout.write(
                "Run `make sync-qdrant-local` to refresh the dev collection from prod."
            )
        else:
            self.stdout.write(self.style.SUCCESS("All sampled search vectors are non-zero"))
