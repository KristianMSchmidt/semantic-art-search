from django.db import models
from django.utils.html import format_html
from artsearch.src.services.museum_clients.utils import (
    get_museum_api_url,
    get_museum_page_url,
)


class MetaDataRaw(models.Model):
    """
    Model to store raw metadata for museum objects.
    """

    museum_slug = models.CharField(max_length=10)
    object_number = models.CharField(
        max_length=100, help_text="Stable and unique public artwork identifier"
    )
    museum_db_id = models.CharField(
        max_length=100, help_text="Internal museum database ID"
    )
    raw_json = models.JSONField()
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="First fetched timestamp"
    )
    last_updated = models.DateTimeField(
        auto_now=True, help_text="Last updated timestamp"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["museum_slug", "object_number"],
                name="uniq_raw_museum_object_number",
            ),
        ]
        indexes = [
            models.Index(fields=["museum_slug"]),  # For museum-specific filtering
        ]

    def __str__(self):
        return f"{self.museum_slug}:{self.object_number}"

    def get_museum_page_link_html(self):
        """HTML link for admin list display."""
        url = get_museum_page_url(
            self.museum_slug, self.object_number, self.museum_db_id
        )
        if url:
            return format_html('<a href="{}" target="_blank">🔗</a>', url)
        return "–"

    get_museum_page_link_html.short_description = "Page"

    def get_museum_api_link_html(self):
        """HTML API link for admin list display."""
        url = get_museum_api_url(
            self.museum_slug, self.object_number, self.museum_db_id
        )
        if url:
            return format_html('<a href="{}" target="_blank">🔗</a>', url)
        return "–"

    get_museum_api_link_html.short_description = "API"


class TransformedData(models.Model):
    """
    Model to store transformed/processed metadata for museum objects.

    This represents the cleaned and standardized data ready for embedding
    generation and vector database upload. Fields match ArtworkPayload structure.
    """

    # Fields copied from MetaDataRaw on transform
    object_number = models.CharField(
        max_length=100, help_text="Stable and unique puclic artwork identifier"
    )  # Required field
    museum_slug = models.CharField(max_length=10)  # Required field
    museum_db_id = models.CharField(
        max_length=100, help_text="Internal museum database ID"
    )  # Required field

    # Extracted fields from raw_json
    searchable_work_types = models.JSONField()  # Required field, list[str]
    thumbnail_url = models.URLField(max_length=500)  # Required field
    title = models.CharField(max_length=500, null=True, blank=True)
    work_types = models.JSONField(
        default=list, help_text="List of work types in original language"
    )  # list[str]
    artist = models.JSONField(default=list)  # list[str]
    production_date_start = models.IntegerField(null=True, blank=True)
    production_date_end = models.IntegerField(null=True, blank=True)
    period = models.CharField(max_length=100, null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)

    # Processing status fields
    image_loaded = models.BooleanField(default=False)
    image_load_failed = models.BooleanField(default=False)

    # Vector storage tracking (for multiple embedding models)
    text_vector_clip = models.BooleanField(default=False)
    image_vector_clip = models.BooleanField(default=False)
    text_vector_jina = models.BooleanField(default=False)
    image_vector_jina = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="First transformed timestamp"
    )
    last_updated = models.DateTimeField(
        auto_now=True, help_text="Last updated timestamp"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["museum_slug", "object_number"],
                name="uniq_transformed_museum_object_number",
            ),
        ]
        indexes = [
            models.Index(fields=["museum_slug"]),  # For museum-specific queries
        ]

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
        elif self.period:
            return self.period
        return "Date unknown"

    def get_museum_page_link_html(self):
        """HTML link for admin list display."""
        url = get_museum_page_url(
            self.museum_slug, self.object_number, self.museum_db_id
        )
        if url:
            return format_html('<a href="{}" target="_blank">🔗</a>', url)
        return "–"

    get_museum_page_link_html.short_description = "Page"

    def get_museum_api_link_html(self):
        """HTML API link for admin list display."""
        url = get_museum_api_url(
            self.museum_slug, self.object_number, self.museum_db_id
        )
        if url:
            return format_html('<a href="{}" target="_blank">🔗</a>', url)
        return "–"

    get_museum_api_link_html.short_description = "API"
