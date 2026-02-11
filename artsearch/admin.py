from django.contrib import admin
from django.utils.html import format_html
from .models import SearchLog, ArtworkStats, ArtworkDescription, ArtMapData, ExampleQuery


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("query", "timestamp", "username")
    list_filter = ("timestamp", "username")
    search_fields = ("query",)
    ordering = ("-timestamp",)


@admin.register(ArtworkStats)
class ArtworkStatsAdmin(admin.ModelAdmin):
    list_display = ("museum_slug", "object_number", "get_work_types_display")
    list_filter = ("museum_slug",)
    search_fields = ("object_number",)
    ordering = ("museum_slug", "object_number")
    readonly_fields = ("museum_slug", "object_number", "searchable_work_types")

    def get_work_types_display(self, obj):
        """Display work types as comma-separated list."""
        return ", ".join(obj.searchable_work_types)

    get_work_types_display.short_description = "Work Types"

    def has_add_permission(self, request):
        """Prevent adding new ArtworkStats entries via admin (should be populated via management command)."""
        return False


@admin.register(ArtworkDescription)
class ArtworkDescriptionAdmin(admin.ModelAdmin):
    list_display = (
        "museum_slug",
        "object_number",
        "created_at",
        "updated_at",
        "get_description_preview",
    )
    list_filter = ("museum_slug", "created_at", "updated_at")
    search_fields = ("object_number", "description")
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")

    def get_description_preview(self, obj):
        """Display first 100 characters of description."""
        return (
            obj.description[:100] + "..."
            if len(obj.description) > 100
            else obj.description
        )

    get_description_preview.short_description = "Description Preview"


@admin.register(ArtMapData)
class ArtMapDataAdmin(admin.ModelAdmin):
    list_display = ("__str__", "created_at", "get_geometry_size", "get_metadata_size")
    ordering = ("-created_at",)
    fields = ("created_at", "get_geometry_size", "get_metadata_size", "get_metadata_preview")
    readonly_fields = ("created_at", "get_geometry_size", "get_metadata_size", "get_metadata_preview")

    def get_geometry_size(self, obj):
        if not obj.geometry:
            return "—"
        size_kb = len(obj.geometry) / 1024
        if size_kb >= 1024:
            return f"{size_kb / 1024:.1f} MB"
        return f"{size_kb:.0f} KB"

    get_geometry_size.short_description = "Geometry Size"

    def get_metadata_size(self, obj):
        if not obj.metadata:
            return "—"
        size_kb = len(obj.metadata) / 1024
        if size_kb >= 1024:
            return f"{size_kb / 1024:.1f} MB"
        return f"{size_kb:.0f} KB"

    get_metadata_size.short_description = "Metadata Size"

    def get_metadata_preview(self, obj):
        if not obj.metadata:
            return "—"
        preview = obj.metadata[:2000]
        if len(obj.metadata) > 2000:
            preview += "..."
        return format_html("<pre style='max-height:300px;overflow:auto;white-space:pre-wrap'>{}</pre>", preview)

    get_metadata_preview.short_description = "Metadata (preview)"

    def has_add_permission(self, request):
        return False


@admin.register(ExampleQuery)
class ExampleQueryAdmin(admin.ModelAdmin):
    list_display = ("query", "is_active", "all_work_types", "created_at")
    list_filter = ("is_active",)
    search_fields = ("query",)
    ordering = ("query",)
    list_editable = ("is_active", "all_work_types")
