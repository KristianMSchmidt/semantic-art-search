from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django_ratelimit.decorators import ratelimit
from artsearch.views.context_builders import (
    build_search_context,
    build_home_context,
    build_work_type_filter_context,
    build_museum_filter_context,
    SearchParams,
)
from artsearch.views.log_utils import log_search_query
from artsearch.src.services import museum_stats_service
from artsearch.src.services.artwork_description.service import generate_description
from artsearch.src.constants.embedding_models import EMBEDDING_MODELS


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
    context["embedding_models"] = EMBEDDING_MODELS
    context["selected_model"] = params.selected_embedding_model
    return render(request, "home.html", context)


def get_artworks_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint for fetching artwork results (initial search or pagination).
    """
    params = SearchParams(request=request)

    # Check for query length validation error
    if params.query_error:
        context = {
            "error_message": params.query_error,
            "error_type": "error",
        }
        return render(request, "partials/artwork_response.html", context)

    if params.offset == 0:
        log_search_query(params)
    context = build_search_context(params, embedding_model=params.selected_embedding_model)
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


@ratelimit(key="ip", rate="15/15m", method="GET")
def get_artwork_description_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint for fetching AI-generated artwork description.

    Rate limited to 15 requests per 15 minutes per IP address to prevent OpenAI API abuse.

    Query params:
    - museum: museum slug (e.g., 'smk')
    - object_number: artwork object number (e.g., 'KMS1')
    - museum_db_id: museum's internal database ID
    - force: if 'true', bypass cache and regenerate description
    """
    # Check if rate limited
    if getattr(request, "limited", False):
        context = {
            "description": None,
            "rate_limited": True,
            "museum_slug": request.GET.get("museum", ""),
            "object_number": request.GET.get("object_number", ""),
        }
        return render(request, "partials/artwork_description.html", context)

    museum_slug = request.GET.get("museum", "")
    object_number = request.GET.get("object_number", "")
    museum_db_id = request.GET.get("museum_db_id", "")
    force_regenerate = request.GET.get("force", "").lower() == "true"

    # Generate AI description
    description = generate_description(
        museum_slug, object_number, museum_db_id, force_regenerate=force_regenerate
    )

    context = {
        "description": description,
        "rate_limited": False,
        "museum_slug": museum_slug,
        "object_number": object_number,
    }

    return render(request, "partials/artwork_description.html", context)


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
