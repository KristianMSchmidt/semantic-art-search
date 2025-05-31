import json
from typing import Any
from urllib.parse import urlencode
from typing import Iterable, Literal
from django.http import HttpRequest
from django.urls import reverse
from artsearch.src.constants import WORK_TYPES_DICT
from artsearch.src.services.museum_stats_service import (
    get_work_type_names,
    aggregate_work_type_count_for_selected_museums,
)
from artsearch.src.utils.get_museums import get_museum_names
from artsearch.src.services.qdrant_service import (
    SearchFunctionArguments,
    get_qdrant_service,
)
from artsearch.src.services.museum_clients.base_client import MuseumAPIClientError

# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()


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


def retrieve_selected(
    all_items: Iterable[str], request: HttpRequest, param_name: str
) -> list[str]:
    """
    Retrieve selected items (work_types or museums) from the request.
    """
    selected_items = request.GET.getlist(param_name)
    # If no items are selected, return all items
    if not selected_items:
        return list(all_items)
    return selected_items


def make_prefilter(
    all_items: Iterable[str],
    selected_items: list[str],
) -> list[str] | None:
    """
    Generalized prefilter function for work types and museums.
    If all items are selected, or none are selected, return None.
    """
    if not selected_items or len(selected_items) == len(list(all_items)):
        return None
    return selected_items


def prepare_work_types_for_dropdown(
    work_types_count: dict[str, int],
) -> list[dict]:
    """
    Prepare work types for the dropdown menu.
    """
    work_types_for_dropdown = []

    for work_type, count in work_types_count.items():
        try:
            eng_plural = WORK_TYPES_DICT[work_type]["eng_plural"]
        except KeyError:
            eng_plural = work_type + "s"  # Fallback to a simple pluralization

        work_types_for_dropdown.append(
            {
                "work_type": work_type,
                "count": count,
                "eng_plural": eng_plural,
            }
        )
    return work_types_for_dropdown


def prepare_initial_label(
    selected_items: list[str],
    all_items: list[str],
    label_type: Literal["work_types", "museums"],
) -> str:
    """
    Prepare the initial label for the dropdowns based on selected items.
    """
    if label_type == "work_types":
        name = "Work Type"
    elif label_type == "museums":
        name = "Museum"
    if not selected_items or len(selected_items) == len(all_items):
        return f"All {name}s"
    elif len(selected_items) == 1:
        return f"1 {name}"
    else:
        return f"{len(selected_items)} {name}s"


def make_url(
    url_name: str,
    offset: int | None = None,
    query: str | None = None,
    selected_work_types: list[str] = [],
    selected_museums: list[str] = [],
) -> str:
    query_params = {}
    if offset is not None:
        query_params["offset"] = offset
    if query:
        query_params["query"] = query
    if selected_work_types:
        query_params["work_types"] = selected_work_types
    if selected_museums:
        query_params["museums"] = selected_museums
    return f"{reverse(url_name)}?{urlencode(query_params, doseq=True)}"


def make_urls(
    offset: int,
    query: str | None,
    selected_work_types: list[str],
    selected_museums: list[str],
) -> dict[str, str]:
    return {
        "search": make_url("search"),
        "more_results": make_url(
            "more-results",
            offset,
            query,
            selected_work_types,
            selected_museums,
        ),
    }


def build_filter_context(request):
    """
    Build the template context for search and dropdown templates
    The 'initial labels' are only used for the search template, the rest is used for both.
    """
    museum_names = get_museum_names()
    selected_museums = retrieve_selected(museum_names, request, "museums")

    work_type_names = get_work_type_names()
    selected_work_types = retrieve_selected(work_type_names, request, "work_types")

    work_type_summary = aggregate_work_type_count_for_selected_museums(selected_museums)
    total_work_count = work_type_summary.total
    prepared_work_types = prepare_work_types_for_dropdown(work_type_summary.work_types)

    initial_work_types_label = prepare_initial_label(
        selected_work_types, work_type_names, "work_types"
    )
    initial_museums_label = prepare_initial_label(
        selected_museums, museum_names, "museums"
    )

    return {
        "total_work_count": total_work_count,
        "work_types": prepared_work_types,
        "initial_museums_label": initial_museums_label,
        "initial_work_types_label": initial_work_types_label,
        "all_work_types_json": json.dumps(work_type_names),
        "selected_work_types_json": json.dumps(selected_work_types),
        "all_museums_json": json.dumps(museum_names),
        "selected_museums_json": json.dumps(selected_museums),
    }


def build_search_context(
    query,
    offset: int,
    limit: int,
    museum_prefilter,
    work_type_prefilter,
) -> dict[Any, Any]:
    """
    Build the context for search results based on the query and filters.
    """
    text_above_results = ""
    results = []
    error_message = None
    error_type = None

    if query is None:
        # This is the initial page load.
        query = ""
        results = qdrant_service.get_random_sample(limit=limit)
        text_above_results = "A glimpse into the archive"

    elif query == "":
        # The user submitted an empty query.
        error_message = "Please enter a search query."
        error_type = "warning"

    else:
        # The user submitted a query.
        search_arguments = SearchFunctionArguments(
            query=query,
            limit=limit,
            offset=offset,
            work_type_prefilter=work_type_prefilter,
            museum_prefilter=museum_prefilter,
        )
        try:
            if qdrant_service.item_exists(query):
                results = qdrant_service.search_similar_images(search_arguments)
            else:
                results = qdrant_service.search_text(search_arguments)

            text_above_results = "Search results (best match first)"
        except MuseumAPIClientError as e:
            error_message = str(e)
            error_type = "warning"
        except Exception as e:
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    return {
        "results": results,
        "text_above_results": text_above_results,
        "error_message": error_message,
        "error_type": error_type,
    }
