from django.db import models


class MetaDataRaw(models.Model):
    """
    Model to store raw metadata for museum objects.

    Fields:
    museum_slug: Slug for the museum (e.g., "smk" for Statens Museum for Kunst)
    museum_object_id: Unique identifier for the object in the museum's collection (could be an accession number or database ID or similar, depending on the museum)
    fetched_at: When the raw data was last fetched from the source (first time or becase a change was detected)
    processed_at: When the raw data was last processed (uploaded to qdrant and embeddings created)
    """

    museum_slug = models.CharField(max_length=10)
    museum_object_id = models.CharField(max_length=100)
    raw_json = models.JSONField(null=True, blank=True)
    raw_xml = models.TextField(null=True, blank=True)
    raw_hash = models.CharField(max_length=64)  # SHA256
    fetched_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True, blank=True
    )  # when the raw data was last processed (uploaded to qdrant and embeddings created)

    class Meta:
        unique_together = ("museum_slug", "museum_object_id")
