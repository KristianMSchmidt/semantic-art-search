from urllib.parse import urlencode
from typing import Callable
from django.http import HttpRequest
from django.urls import reverse
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.views.constants import ARTWORK_TYPES


def retrieve_query(request: HttpRequest) -> str | None:
    query = request.GET.get("query")
    if query is None:
        return None
    return query.strip()


def retrieve_offset(request: HttpRequest) -> int:
    offset = request.GET.get("offset", None)
    assert offset is not None
    offset = int(offset)
    return offset


def retrieve_search_action(request: HttpRequest) -> str:
    search_action = request.GET.get("search_action")
    assert search_action in ["text-search", "find-similar"]
    return search_action


def retrieve_search_function(
    search_action: str, qdrant_service: QdrantService
) -> Callable:
    if search_action == "text-search":
        return qdrant_service.search_text
    else:
        return qdrant_service.search_similar_images


def retrieve_selected_artwork_types(request: HttpRequest) -> list[str]:
    selected_artwork_types = request.GET.getlist("artwork_types")
    # If no artwork types are selected, return all artwork types
    if not selected_artwork_types:
        return list(map(str, ARTWORK_TYPES.keys()))
    return selected_artwork_types


def make_artwork_types_prefilter(
    selected_artwork_types: list[str],
) -> list[str] | None:
    # If all artwork types are selected, or none are selected, return None (We don't need to filter by artwork type)
    if not selected_artwork_types or len(selected_artwork_types) == len(ARTWORK_TYPES):
        return None
    return [
        ARTWORK_TYPES[int(artwork_type)]["dk_name"].lower()
        for artwork_type in selected_artwork_types
    ]


def make_url(
    url_name: str,
    offset: int | None = None,
    search_action: str | None = None,
    query: str | None = None,
    selected_artwork_types: list[str] = [],
) -> str:
    query_params = {}
    if offset is not None:
        query_params["offset"] = offset
    if search_action is not None:
        query_params["search_action"] = search_action
    if query:
        query_params["query"] = query
    if selected_artwork_types:
        query_params["artwork_types"] = selected_artwork_types

    return f"{reverse(url_name)}?{urlencode(query_params, doseq=True)}"


def make_urls(
    offset: int,
    search_action: str,
    query: str | None,
    selected_artwork_types: list[str],
) -> dict[str, str]:
    return {
        "home": make_url("text-search"),
        "text_search": make_url("text-search"),
        "find_similar": make_url("find-similar"),
        "search_action": make_url(search_action),
        "more_results": make_url(
            "more-results", offset, search_action, query, selected_artwork_types
        ),
    }
