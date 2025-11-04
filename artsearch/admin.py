from django.contrib import admin
from .models import SearchLog, ArtworkStats


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
