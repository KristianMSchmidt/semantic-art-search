from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit

from artsearch.src.config import config
from artsearch.src.constants.embedding_models import validate_embedding_model
from artsearch.src.constants.museums import SUPPORTED_MUSEUMS
from artsearch.src.constants.search import MAX_QUERY_LENGTH
from artsearch.src.constants.work_types import SEARCHABLE_WORK_TYPES
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.services.search_service import handle_search
from artsearch.src.utils.qdrant_formatting import format_payload
from artsearch.views.views import get_client_ip


qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)


def museums_view(request):
    return JsonResponse({
        "museums": [
            {"slug": m["slug"], "full_name": m["full_name"]}
            for m in SUPPORTED_MUSEUMS
        ],
    })


def work_types_view(request):
    return JsonResponse({
        "work_types": sorted(SEARCHABLE_WORK_TYPES),
    })


def _parse_search_params(request) -> dict:
    """Parse query parameters shared by search endpoints.

    Returns a dict whose keys match handle_search kwargs.
    """
    try:
        offset = int(request.GET.get("offset", 0))
    except (ValueError, TypeError):
        offset = 0

    try:
        limit = min(int(request.GET.get("limit", 24)), 24)
    except (ValueError, TypeError):
        limit = 24

    return {
        "offset": offset,
        "limit": limit,
        "museums": request.GET.getlist("museums") or None,
        "work_types": request.GET.getlist("work_types") or None,
        "embedding_model": validate_embedding_model(request.GET.get("model", "auto")),
    }


def artwork_detail_view(request, museum_slug: str, object_number: str):
    items = qdrant_service.get_items_by_object_number(
        object_number=object_number,
        object_museum=museum_slug,
        with_payload=True,
        limit=1,
    )

    if not items:
        return JsonResponse({"error": "Artwork not found"}, status=404)

    payload = items[0].payload

    if payload is None:
        return JsonResponse({"error": "Artwork not found"}, status=404)

    return JsonResponse(format_payload(payload))


@ratelimit(key=get_client_ip, rate="30/m", method="GET", block=False)
@ratelimit(key=get_client_ip, rate="200/h", method="GET", block=False)
def similar_view(request, museum_slug: str, object_number: str):
    if getattr(request, "limited", False):
        return JsonResponse(
            {"error": "Too many requests. Please try again later."}, status=429
        )

    params = _parse_search_params(request)

    search_results = handle_search(
        query=f"{museum_slug}:{object_number}",
        **params,
    )

    if search_results["error_message"]:
        status = 404 if "No artworks found" in search_results["error_message"] else 400
        return JsonResponse({"error": search_results["error_message"]}, status=status)

    return JsonResponse({
        "results": search_results["results"],
        "total_works": search_results["total_works"],
        "museum_slug": museum_slug,
        "object_number": object_number,
        "offset": params["offset"],
        "limit": params["limit"],
    })


@ratelimit(key=get_client_ip, rate="30/m", method="GET", block=False)
@ratelimit(key=get_client_ip, rate="200/h", method="GET", block=False)
def search_view(request):
    if getattr(request, "limited", False):
        return JsonResponse(
            {"error": "Too many requests. Please try again later."}, status=429
        )

    query = request.GET.get("query", "").strip()
    if not query:
        return JsonResponse({"error": "query parameter is required"}, status=400)

    if len(query) > MAX_QUERY_LENGTH:
        return JsonResponse(
            {"error": f"Query too long (max {MAX_QUERY_LENGTH} characters)"},
            status=400,
        )

    params = _parse_search_params(request)

    search_results = handle_search(query=query, **params)

    if search_results["error_message"]:
        return JsonResponse({"error": search_results["error_message"]}, status=400)

    return JsonResponse({
        "results": search_results["results"],
        "total_works": search_results["total_works"],
        "query": query,
        "offset": params["offset"],
        "limit": params["limit"],
    })
