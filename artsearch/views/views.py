import random

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django_ratelimit.decorators import ratelimit

from artsearch.views.context_builders import (
    build_search_context,
    build_home_context,
    build_work_type_filter_context,
    build_museum_filter_context,
    get_active_example_queries,
    SearchParams,
)
from artsearch.views.log_utils import log_search_query
from artsearch.src.services.artwork_description.service import generate_description
from artsearch.src.cache_registry import clear_all_caches
from artsearch.src.constants.embedding_models import EMBEDDING_MODELS
from artsearch.src.constants.ui import EXAMPLE_QUERY_COUNTS


def get_client_ip(group, request):
    """Get real client IP from X-Forwarded-For header (set by nginx proxy)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
    queries = get_active_example_queries()
    shuffled_queries = random.sample(queries, len(queries))
    context = build_home_context(params=params, example_queries=shuffled_queries)
    context["embedding_models"] = EMBEDDING_MODELS
    context["selected_model"] = params.selected_embedding_model
    context["example_query_counts"] = EXAMPLE_QUERY_COUNTS
    return render(request, "home.html", context)


@ratelimit(key=get_client_ip, rate="30/m", method="GET", block=False)
@ratelimit(key=get_client_ip, rate="200/h", method="GET", block=False)
def get_artworks_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint for fetching artwork results (initial search or pagination).

    Rate limited to 30/min and 200/hour per IP address to prevent Jina API abuse.
    """
    # Check if rate limited
    if getattr(request, "limited", False):
        context = {
            "error_message": "Too many searches. Please wait a moment before trying again.",
            "error_type": "warning",
        }
        return render(request, "partials/artwork_response.html", context)

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
    context = build_search_context(
        params, embedding_model=params.selected_embedding_model
    )
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


@ratelimit(key=get_client_ip, rate="5/m", method="GET", block=False)
@ratelimit(key=get_client_ip, rate="50/h", method="GET", block=False)
def get_artwork_description_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint for fetching AI-generated artwork description.

    Rate limited to 5/min and 50/hour per IP address to prevent OpenAI API abuse.

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
    """Admin-only endpoint to clear all registered LRU caches."""
    count = clear_all_caches()
    return HttpResponse(f"Cleared {count} caches successfully", content_type="text/plain")
