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


class ArtworkDescription(models.Model):
    """
    Cached AI-generated artwork descriptions.
    Stores OpenAI GPT-4o vision descriptions to avoid redundant API calls.

    Design: One row per artwork. Uses same composite key as ArtworkStats.
    The unique constraint automatically creates a composite index on
    (museum_slug, object_number) which optimizes lookups.
    """

    museum_slug = models.CharField(max_length=10)
    object_number = models.CharField(
        max_length=100, help_text="Stable and unique public artwork identifier"
    )
    description = models.TextField(help_text="AI-generated artwork description")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["museum_slug", "object_number"],
                name="uniq_description_museum_object",
            ),
        ]

    def __str__(self):
        return f"{self.museum_slug}:{self.object_number}"


class ArtMapData(models.Model):
    """
    Stores pre-computed UMAP 2D coordinates for the art map visualization.
    One row per generation run. Latest row is served to the frontend.
    Stored in PostgreSQL so data persists across deploys (unlike static files).
    """

    data = models.TextField(help_text="Raw JSON string of map data")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def version(self):
        return self.created_at.strftime("%Y%m%d%H%M%S")

    def __str__(self):
        size_kb = len(self.data) / 1024
        return f"ArtMapData ({size_kb:.0f} KB, {self.created_at.strftime('%Y-%m-%d %H:%M')})"


class ExampleQuery(models.Model):
    """
    Example search queries displayed on the homepage.
    Stored in database to allow editing in production without redeployment.
    """

    query = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(
        default=True, help_text="Whether this query is shown on the homepage"
    )
    all_work_types = models.BooleanField(
        default=False,
        help_text="If true, select all work types when clicked. If false, select only paintings.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["query"]
        verbose_name = "Example Query"
        verbose_name_plural = "Example Queries"

    def __str__(self):
        return self.query
