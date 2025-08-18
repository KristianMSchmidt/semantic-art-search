from django.contrib import admin
from .models import MetaDataRaw, TransformedData


@admin.register(MetaDataRaw)
class MetaDataRawAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "museum_slug",
        "museum_object_id",
        "created_at",
        "last_updated",
        "raw_hash",
    )
    list_filter = ("museum_slug", "created_at", "last_updated")
    search_fields = ("museum_slug", "museum_object_id")
    ordering = ("-last_updated",)
    readonly_fields = ("raw_hash", "created_at", "last_updated")

    def has_add_permission(self, request):
        """Prevent adding new MetaDataRaw entries via the admin interface."""
        return False


@admin.register(TransformedData)
class TransformedDataAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "object_number",
        "museum_slug",
        "created_at",
        "last_updated",
        "source_raw_hash",
    )
    list_filter = ("museum_slug", "created_at")
    search_fields = ("object_number", "title", "museum_slug")
    ordering = ("-created_at",)
    exclude = ("raw_data",)  # Exclude for performance
    readonly_fields = ("created_at", "last_updated", "source_raw_hash")

    def has_add_permission(self, request):
        """Prevent adding new TransformedData entries via the admin interface."""
        return False
