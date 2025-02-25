from urllib.parse import urlencode
from typing import Callable
from django.http import HttpRequest
from django.urls import reverse
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.views.constants import ARTWORK_TYPES


def retrieve_offset(request: HttpRequest) -> int:
    offset = request.GET.get("offset", None)
    assert offset is not None
    offset = int(offset)
    return offset


def retrieve_search_action_url(request: HttpRequest) -> str:
    search_action_url = request.GET.get("search_action_url")
    assert search_action_url in ["text-search", "find-similar"]
    return search_action_url


def retrieve_search_function(
    search_action_url: str, qdrant_service: QdrantService
) -> Callable:
    if search_action_url == "text-search":
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
    search_action_url: str | None = None,
    query: str | None = None,
    selected_artwork_types: list[str] = [],
) -> str:
    query_params = {}
    if offset is not None:
        query_params["offset"] = offset
    if search_action_url is not None:
        query_params["search_action_url"] = search_action_url
    if query:
        query_params["query"] = query
    if selected_artwork_types:
        query_params["artwork_types"] = selected_artwork_types

    return f"{reverse(url_name)}?{urlencode(query_params, doseq=True)}"


def make_urls(
    offset: int,
    search_action_url: str,
    query: str | None,
    selected_artwork_types: list[str],
) -> dict[str, str]:
    home_url = make_url("home", selected_artwork_types=selected_artwork_types)
    text_search_url = make_url(
        "text-search", selected_artwork_types=selected_artwork_types
    )
    find_similar_url = make_url(
        "find-similar", selected_artwork_types=selected_artwork_types
    )
    more_results_url = make_url(
        "more-results", offset, search_action_url, query, selected_artwork_types
    )
    return {
        "home": home_url,
        "text_search": text_search_url,
        "find_similar": find_similar_url,
        "more_results": more_results_url,
    }
