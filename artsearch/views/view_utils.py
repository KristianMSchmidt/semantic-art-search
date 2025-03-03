from urllib.parse import urlencode
from typing import Callable
from django.http import HttpRequest
from django.urls import reverse
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.constants import WORK_TYPES


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


def retrieve_selected_work_types(request: HttpRequest) -> list[str]:
    selected_work_types = request.GET.getlist("work_types")
    # If no work types are selected, return all work types
    if not selected_work_types:
        return list(map(str, WORK_TYPES.keys()))
    return selected_work_types


def make_work_types_prefilter(
    selected_work_types: list[str],
) -> list[str] | None:
    # If all work types are selected, or none are selected, return None (We don't need to filter by work type)
    if not selected_work_types or len(selected_work_types) == len(WORK_TYPES):
        return None
    return [WORK_TYPES[int(work_type)].dk_name for work_type in selected_work_types]


def make_url(
    url_name: str,
    offset: int | None = None,
    search_action: str | None = None,
    query: str | None = None,
    selected_work_types: list[str] = [],
) -> str:
    query_params = {}
    if offset is not None:
        query_params["offset"] = offset
    if search_action is not None:
        query_params["search_action"] = search_action
    if query:
        query_params["query"] = query
    if selected_work_types:
        query_params["work_types"] = selected_work_types

    return f"{reverse(url_name)}?{urlencode(query_params, doseq=True)}"


def make_urls(
    offset: int,
    search_action: str,
    query: str | None,
    selected_work_types: list[str],
) -> dict[str, str]:
    return {
        "home": make_url("text-search"),
        "text_search": make_url("text-search"),
        "find_similar": make_url("find-similar"),
        "search_action": make_url(search_action),
        "more_results": make_url(
            "more-results", offset, search_action, query, selected_work_types
        ),
    }
