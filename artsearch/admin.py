from django.contrib import admin
from .models import SearchLog


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("query", "timestamp", "username")
    list_filter = ("timestamp", "username")
    search_fields = ("query",)
    ordering = ("-timestamp",)
