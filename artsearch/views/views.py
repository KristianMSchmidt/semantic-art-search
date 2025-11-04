from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from artsearch.views.context_builders import (
    build_search_context,
    build_home_context,
    build_work_type_filter_context,
    build_museum_filter_context,
    SearchParams,
)
from artsearch.views.log_utils import log_search_query
from artsearch.src.services import museum_stats_service


def home_view(request: HttpRequest) -> HttpResponse:
    """
    Render the main homepage with the search form and initial context.

    This view handles all non‐HTMX GET requests to "/". It builds and returns
    the full `home.html` page including:
      - the search form
      - example queries
      - empty placeholder for search results

    It does _not_ process actual search submissions; those are handled by
    `get_artworks_view` via HTMX.
    """
    params = SearchParams(request=request)
    context = build_home_context(params=params)
    return render(request, "home.html", context)


def get_artworks_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint for fetching artwork results (initial search or pagination).
    """
    params = SearchParams(request=request)
    if params.offset == 0:
        log_search_query(params)
    context = build_search_context(params)
    return render(request, "partials/artwork_response.html", context)


def update_work_types(request):
    """
    HTMX view that updates the work type dropdown based on selected museums.
    """
    params = SearchParams(request=request)
    context = {
        "filter_ctx": build_work_type_filter_context(params),
    }
    return render(request, "partials/dropdown.html", context)


def update_museums(request):
    """
    HTMX view that updates the museum dropdown based on selected work types.
    """
    params = SearchParams(request=request)
    context = {
        "filter_ctx": build_museum_filter_context(params),
    }
    return render(request, "partials/dropdown.html", context)


@staff_member_required
def clear_cache(request):
    """
    Admin-only endpoint to clear all LRU caches in museum_stats_service.

    Useful after running load_artwork_stats to refresh stats without restarting the app.
    """
    # Clear all cached functions
    museum_stats_service.get_work_type_names.cache_clear()
    museum_stats_service.aggregate_work_type_count_for_selected_museums.cache_clear()
    museum_stats_service.aggregate_museum_count_for_selected_work_types.cache_clear()
    museum_stats_service.get_total_works_for_filters.cache_clear()

    return HttpResponse("Cache cleared successfully", content_type="text/plain")
