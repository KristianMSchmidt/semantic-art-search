from django.contrib import admin
from .models import MetaDataRaw


@admin.register(MetaDataRaw)
class MetaDataRawAdmin(admin.ModelAdmin):
    list_display = (
        "museum_slug",
        "museum_object_id",
        "fetched_at",
        "processed_at",
        "raw_hash",
    )
    list_filter = ("museum_slug", "fetched_at")
    search_fields = ("museum_slug", "museum_object_id")
    ordering = ("-fetched_at",)
    readonly_fields = ("raw_hash",)

    def has_add_permission(self, request):
        return False
