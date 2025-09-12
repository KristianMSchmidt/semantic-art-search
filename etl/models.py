from django.db import models


class MetaDataRaw(models.Model):
    """
    Model to store raw metadata for museum objects.
    """

    museum_slug = models.CharField(max_length=10)
    museum_object_id = models.CharField(max_length=100)
    raw_json = models.JSONField()
    raw_hash = models.CharField(max_length=64)  # SHA256
    created_at = models.DateTimeField(auto_now_add=True)  # first fetched timestamp
    last_updated = models.DateTimeField(auto_now=True)  # last updated timestamp

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["museum_slug", "museum_object_id"],
                name="uniq_raw_museum_object",
            ),
        ]
        indexes = [
            models.Index(fields=["museum_slug"]),  # For museum-specific filtering
            models.Index(
                fields=["raw_hash"]
            ),  # For hash comparisons in staleness checks
        ]


class TransformedData(models.Model):
    """
    Model to store transformed/processed metadata for museum objects.

    This represents the cleaned and standardized data ready for embedding
    generation and vector database upload. Fields match ArtworkPayload structure.
    """

    # Reference to raw data
    raw_data = models.OneToOneField(MetaDataRaw, on_delete=models.CASCADE)

    # Record which raw version this transform corresponds to:
    source_raw_hash = models.CharField(
        max_length=64,
    )  # copy of MetaDataRaw.raw_hash at transform time

    # Required fields
    object_number = models.CharField(max_length=100)  # Required field
    thumbnail_url = models.URLField(max_length=500)  # Required field
    museum_slug = models.CharField(max_length=10)  # Required field
    searchable_work_types = models.JSONField()  # Required field, list[str]

    # Other fields
    title = models.CharField(max_length=500, null=True, blank=True)
    work_types = models.JSONField(default=list)  # list[str]
    artist = models.JSONField(default=list)  # list[str]
    production_date_start = models.IntegerField(null=True, blank=True)
    production_date_end = models.IntegerField(null=True, blank=True)
    period = models.CharField(max_length=100, null=True, blank=True)
    museum_db_id = models.CharField(max_length=100, null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)

    # Processing status fields
    image_loaded = models.BooleanField(default=False)
    thumbnail_url_hash = models.CharField(
        max_length=64, 
        null=True, 
        blank=True,
        help_text="SHA256 hash of thumbnail_url to detect changes"
    )

    # Vector storage tracking (for multiple embedding models)
    text_vector_clip = models.BooleanField(default=False)
    image_vector_clip = models.BooleanField(default=False)
    text_vector_jina = models.BooleanField(default=False)
    image_vector_jina = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)  # first transform
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.museum_slug}:{self.object_number} - {self.get_primary_title()}"

    def get_primary_title(self):
        """Get the primary title from the titles list."""
        if self.title:
            return self.title
        return "Untitled"

    def get_artists(self):
        """Get the artist names"""
        if len(self.artist) > 0:
            return ", ".join(self.artist)
        return "Unknown Artist"

    def get_period(self):
        """Get formatted date display."""
        if self.production_date_start and self.production_date_end:
            if self.production_date_start == self.production_date_end:
                return str(self.production_date_start)
            return f"{self.production_date_start} - {self.production_date_end}"
        elif self.production_date_start:
            return str(self.production_date_start)
        return "Date unknown"

    class Meta:
        indexes = [
            models.Index(fields=["source_raw_hash"]),  # For staleness comparisons
            models.Index(fields=["museum_slug"]),  # For museum-specific queries
        ]

    @property
    def is_stale(self) -> bool:
        """
        Check if the transformed data is stale compared to the raw data.
        """
        return self.raw_data.raw_hash != self.source_raw_hash
