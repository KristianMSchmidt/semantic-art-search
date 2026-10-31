import json
import logging
import random
from functools import lru_cache
from urllib.parse import urlencode

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from artsearch.views.context_builders import (
    build_search_context,
    make_home_url,
    build_home_context,
    build_work_type_filter_context,
    build_museum_filter_context,
    get_active_example_queries,
    SearchParams,
)
from artsearch.views.log_utils import log_search_query
from artsearch.src.services.artwork_description.cache import get_cached_description
from artsearch.src.services.artwork_description.service import generate_description
from artsearch.src.services.image_upload_service import (
    DailyCapReached,
    ImageUploadError,
    embed_upload,
    get_uploaded_image_vector,
)
from artsearch.src.utils.get_museums import get_museum_slugs
from artsearch.src.utils.iiif import (
    get_artwork_iiif_service_url,
    get_iiif_info_url,
    get_iiif_sized_image_url,
)
from artsearch.src.services.qdrant_service import QdrantService, SearchFunctionArguments
from artsearch.src.utils.qdrant_formatting import format_payload
from artsearch.src.cache_registry import clear_all_caches, register_cache
from artsearch.src.config import config
from artsearch.src.constants.ui import EXAMPLE_QUERY_COUNTS
from artsearch.models import ArtMapData

logger = logging.getLogger(__name__)

SIMILAR_ARTWORKS_ON_PAGE = 12
# Deep Qdrant offsets get slow; nobody pages this far through similar artworks
MAX_SIMILAR_OFFSET = 500
# Longest side (px) of the IIIF image shown on artwork pages instead of the
# 800px bucket thumbnail; about 0.25-1 MB per image
LARGE_IMAGE_SIZE = 1600


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
    context["selected_model"] = params.selected_search_mode
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

    image_vector = None
    if params.image_key:
        image_vector = get_uploaded_image_vector(params.image_key)
        if image_vector is None:
            context = {
                "error_message": "Your image search has expired. Please upload the image again.",
                "error_type": "warning",
            }
            return render(request, "partials/artwork_response.html", context)
    if params.offset == 0:
        log_search_query(params, image_search=image_vector is not None)
    context = build_search_context(
        params, search_mode=params.selected_search_mode, image_vector=image_vector
    )
    response = render(request, "partials/artwork_response.html", context)
    if params.offset == 0:
        # Keep the browser URL in sync with the search so refresh and
        # sharing reproduce it (pagination requests leave it alone)
        response["HX-Replace-Url"] = make_home_url(params)
    return response


@require_POST
@ratelimit(key=get_client_ip, rate="10/m", method="POST", block=False)
@ratelimit(key=get_client_ip, rate="100/h", method="POST", block=False)
def upload_image_view(request: HttpRequest) -> JsonResponse:
    """
    Embed an uploaded image for image search and return the key of its cached
    embedding. The client then runs the search through get_artworks_view with
    `image=<key>`, so filters and pagination work as for text searches.

    The image is processed in memory and never stored. Rate limited more
    tightly than text search, since image embeddings cost more Jina tokens.
    """
    if getattr(request, "limited", False):
        return JsonResponse(
            {"error": "Too many image searches. Please wait a moment before trying again."},
            status=429,
        )
    try:
        image_key, _ = embed_upload(request.FILES.get("image"))
    except DailyCapReached as e:
        return JsonResponse({"error": str(e)}, status=429)
    except ImageUploadError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"image_key": image_key})


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


def get_artwork(museum_slug: str, object_number: str) -> dict | None:
    """Fetch a single artwork formatted for display, or None if it doesn't exist."""
    if museum_slug not in get_museum_slugs():
        return None
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)
    items = qdrant_service.get_items_by_object_number(
        object_number=object_number,
        object_museum=museum_slug,
        with_payload=True,
        limit=1,
    )
    if not items or items[0].payload is None:
        return None
    return format_payload(items[0].payload)


def get_similar_artworks(
    museum_slug: str, object_number: str, limit: int, offset: int = 0
) -> tuple[list[dict], int]:
    """
    Visually similar artworks, excluding the artwork itself, plus the offset
    to fetch the next batch from.

    Uses the stored image vector, so no embedding API call is made. Returns no
    artworks on failure so the artwork page still renders.
    """
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)
    search_args = SearchFunctionArguments(
        query=f"{museum_slug}:{object_number}",
        limit=limit + 1,  # room for the artwork itself, which is filtered out
        offset=offset,
        work_type_prefilter=None,
        museum_prefilter=None,
        object_number=object_number,
        object_museum=museum_slug,
    )
    try:
        results = qdrant_service.search_similar_images(search_args)
    except Exception:
        logger.exception(f"Similar search failed for {museum_slug}:{object_number}")
        return [], offset

    similar: list[dict] = []
    consumed = 0
    for result in results:
        if len(similar) == limit:
            break
        consumed += 1
        if not result["is_query_artwork"]:
            similar.append(result)
    return similar, offset + consumed


def _similar_artworks_context(
    museum_slug: str, object_number: str, offset: int = 0
) -> dict:
    similar, next_offset = get_similar_artworks(
        museum_slug, object_number, SIMILAR_ARTWORKS_ON_PAGE, offset
    )
    more_url = None
    if len(similar) == SIMILAR_ARTWORKS_ON_PAGE:
        more_url = (
            reverse("artwork-similar", args=[museum_slug, object_number])
            + f"?offset={next_offset}"
        )
    return {"similar_artworks": similar, "similar_more_url": more_url}


def artwork_page_view(
    request: HttpRequest, museum_slug: str, object_number: str
) -> HttpResponse:
    """
    Shareable page for a single artwork: image, metadata, similar artworks and
    the AI description.

    Only an already cached description is shown; generating a new one is left
    to an explicit click, so crawlers visiting many pages don't trigger OpenAI calls.
    """
    artwork = get_artwork(museum_slug, object_number)
    if artwork is None:
        raise Http404("Artwork not found")

    description = get_cached_description(museum_slug, object_number)
    date = f" ({artwork['production_date']})" if artwork["production_date"] else ""
    meta_description = description or (
        f"{artwork['title']} by {artwork['artist']}{date}. {artwork['museum']}."
    )
    # High-resolution image served by the museum's IIIF server, if it has one
    iiif_service_url = get_artwork_iiif_service_url(museum_slug, object_number)
    context = {
        "artwork": artwork,
        "iiif_info_url": iiif_service_url and get_iiif_info_url(iiif_service_url),
        "large_image_url": iiif_service_url
        and get_iiif_sized_image_url(iiif_service_url, LARGE_IMAGE_SIZE),
        "description": description,
        "meta_description": meta_description,
        "description_url": reverse("get-artwork-description")
        + "?"
        + urlencode(
            {
                "museum": museum_slug,
                "object_number": object_number,
                "museum_db_id": artwork["museum_db_id"],
            }
        ),
        "canonical_url": request.build_absolute_uri(
            reverse("artwork-page", args=[museum_slug, object_number])
        ),
        "map_url": make_map_url(museum_slug, object_number),
        **_similar_artworks_context(museum_slug, object_number),
    }
    return render(request, "artwork.html", context)


@ratelimit(key=get_client_ip, rate="30/m", method="GET", block=False)
@ratelimit(key=get_client_ip, rate="200/h", method="GET", block=False)
def artwork_similar_view(
    request: HttpRequest, museum_slug: str, object_number: str
) -> HttpResponse:
    """
    HTMX endpoint for the artwork page's "Show more" similar artworks.

    Rate limited and capped like the REST similar endpoint; when limited (or
    past the cap) it returns no more cards, which also hides the button.
    """
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except ValueError:
        offset = 0
    if (
        getattr(request, "limited", False)
        or museum_slug not in get_museum_slugs()
        or offset > MAX_SIMILAR_OFFSET
    ):
        return render(request, "partials/similar_artworks.html", {})
    context = _similar_artworks_context(museum_slug, object_number, offset)
    return render(request, "partials/similar_artworks.html", context)


def robots_txt_view(request: HttpRequest) -> HttpResponse:
    """Point crawlers at the sitemap and keep them off search endpoints (Jina API cost)."""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /artworks/",
        "Disallow: /htmx/",
        "Disallow: /artwork/*/similar/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap-index'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


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


def get_cached_artwork_description_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX/fetch endpoint for the artwork popup: return an already generated
    description, or 204 if there is none. Never calls OpenAI, so it isn't
    rate limited like get_artwork_description_view.
    """
    museum_slug = request.GET.get("museum", "")
    object_number = request.GET.get("object_number", "")
    description = get_cached_description(museum_slug, object_number)
    if description is None:
        return HttpResponse(status=204)
    context = {
        "description": description,
        "rate_limited": False,
        "museum_slug": museum_slug,
        "object_number": object_number,
    }
    return render(request, "partials/artwork_description.html", context)


def get_large_image_url_view(request: HttpRequest) -> HttpResponse:
    """
    Fetch endpoint for the artwork popup: the URL of a larger IIIF image from the
    museum, or 204 if it has none. DB-only, so not rate limited.
    """
    museum_slug = request.GET.get("museum", "")
    object_number = request.GET.get("object_number", "")
    iiif_service_url = get_artwork_iiif_service_url(museum_slug, object_number)
    if iiif_service_url is None:
        return HttpResponse(status=204)
    return JsonResponse(
        {"url": get_iiif_sized_image_url(iiif_service_url, LARGE_IMAGE_SIZE)}
    )


def make_map_url(museum_slug: str, object_number: str) -> str:
    """Art map URL that flies to this artwork and selects it ("Show on map")."""
    return f"{reverse('art-map')}?{urlencode({'artwork': f'{museum_slug}/{object_number}'})}"


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
