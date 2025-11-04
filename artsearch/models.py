from django.db import models
from django.contrib.postgres.indexes import GinIndex


class SearchLog(models.Model):
    query = models.TextField(editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    username = models.CharField(max_length=255, editable=False, blank=True, null=True)

    def __str__(self):
        return f"{self.query} @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class ArtworkStats(models.Model):
    """
    Denormalized stats table for fast artwork counting queries.
    One row per artwork. Enables O(1) database queries instead of O(n) Qdrant scans.

    Supports queries:
    - Count artworks per museum
    - Count artworks per work type (with deduplication)
    - Count artworks matching museum + work type filters

    Design: One row per artwork (not per work type) to avoid double-counting
    artworks with multiple work types. This makes counting queries simple and fast.
    """

    museum_slug = models.CharField(max_length=10)
    object_number = models.CharField(
        max_length=100, help_text="Stable and unique public artwork identifier"
    )
    searchable_work_types = models.JSONField(
        help_text="List of searchable work types for this artwork"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["museum_slug", "object_number"],
                name="uniq_stats_museum_object",
            ),
        ]
        indexes = [
            # Fast museum filtering
            models.Index(fields=["museum_slug"]),
            # PostgreSQL GIN index with jsonb_path_ops for optimal JSONB array queries
            # Optimized for @> (contains) and ?| (overlap) operators used in work type filtering
            # jsonb_path_ops uses less space and is faster than default jsonb_ops for these operations
            GinIndex(
                fields=["searchable_work_types"],
                name="idx_searchable_work_types_gin",
                opclasses=["jsonb_path_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.museum_slug}:{self.object_number}"
