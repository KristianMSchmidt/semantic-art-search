import json
import random
from functools import lru_cache

from django.http import HttpRequest, HttpResponse, JsonResponse
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
from artsearch.src.cache_registry import clear_all_caches, register_cache
from artsearch.src.config import config
from artsearch.src.constants.embedding_models import EMBEDDING_MODELS
from artsearch.src.constants.ui import EXAMPLE_QUERY_COUNTS
from artsearch.models import ArtMapData


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


def art_map_view(request: HttpRequest) -> HttpResponse:
    from artsearch.src.constants.museums import (
        MUSEUM_SLUGS,
        MUSEUM_NAMES,
        WORK_TYPE_LABELS,
    )

    map_data = ArtMapData.objects.first()
    context = {
        "bucket_region": config.aws_bucket_region,
        "bucket_name": config.bucket_name_app,
        "map_data_version": map_data.version if map_data else "",
        "museum_slugs_json": json.dumps(MUSEUM_SLUGS),
        "museum_names_json": json.dumps(MUSEUM_NAMES),
        "work_type_labels_json": json.dumps(WORK_TYPE_LABELS),
    }
    return render(request, "map.html", context)


@register_cache
@lru_cache(maxsize=2)
def _get_map_geometry(version: str = "") -> bytes | None:
    map_data = ArtMapData.objects.first()
    return bytes(map_data.geometry) if map_data and map_data.geometry else None


@register_cache
@lru_cache(maxsize=2)
def _get_map_metadata(version: str = "") -> str | None:
    map_data = ArtMapData.objects.first()
    return map_data.metadata if map_data else None


def art_map_geometry_view(request: HttpRequest) -> HttpResponse:
    version = request.GET.get("v", "")
    data = _get_map_geometry(version)
    if data is None:
        return JsonResponse({"error": "No map data available"}, status=404)

    response = HttpResponse(data, content_type="application/octet-stream")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def art_map_data_view(request: HttpRequest) -> HttpResponse:
    version = request.GET.get("v", "")
    data = _get_map_metadata(version)
    if data is None:
        return JsonResponse({"error": "No map data available"}, status=404)

    response = HttpResponse(data, content_type="application/json")
    response["Cache-Control"] = "public, max-age=86400"
    return response


@staff_member_required
def clear_cache(request):
    """Admin-only endpoint to clear all registered LRU caches."""
    count = clear_all_caches()
    return HttpResponse(
        f"Cleared {count} caches successfully", content_type="text/plain"
    )


@staff_member_required
def sentry_test(request):
    """Admin-only endpoint to test Sentry error reporting."""
    raise Exception("Sentry test error - this is intentional")
