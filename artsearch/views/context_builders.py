from dataclasses import dataclass
import json
from typing import Any
from django.http import HttpRequest
from artsearch.src.services.museum_stats_service import (
    get_work_type_names,
    aggregate_work_type_count_for_selected_museums,
)
from artsearch.src.utils.get_museums import get_museum_names
from artsearch.src.services.qdrant_service import (
    SearchFunctionArguments,
    get_qdrant_service,
)
from artsearch.views.view_utils import (
    retrieve_selected,
    retrieve_query,
    prepare_work_types_for_dropdown,
    prepare_initial_label,
    make_prefilter,
    make_urls,
)
from artsearch.src.services.museum_clients.base_client import MuseumAPIClientError
from artsearch.src.constants import SUPPORTED_MUSEUMS


RESULTS_PER_PAGE = 20


@dataclass
class SearchParams:
    """Parameters for the handle_search view"""

    request: HttpRequest
    offset: int = 0
    limit: int = RESULTS_PER_PAGE
    example_queries: list[str] | None = None


# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()


def handle_search(
    query: str | None,
    offset: int,
    limit: int,
    museum_prefilter,
    work_type_prefilter,
) -> dict[Any, Any]:
    """
    Handle the search logic based on the provided query and filters.
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
        except Exception:
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    return {
        "results": results,
        "text_above_results": text_above_results,
        "error_message": error_message,
        "error_type": error_type,
    }


def build_main_context(params: SearchParams) -> dict[Any, Any]:
    """
    Build the main context for the search view.
    """
    request = params.request
    offset = params.offset
    limit = params.limit
    query = retrieve_query(request)

    museum_names = get_museum_names()
    selected_museums = retrieve_selected(museum_names, request, "museums")

    work_type_names = get_work_type_names()
    selected_work_types = retrieve_selected(work_type_names, request, "work_types")

    search_results = handle_search(
        query=query,
        offset=offset,
        limit=limit,
        museum_prefilter=make_prefilter(museum_names, selected_museums),
        work_type_prefilter=make_prefilter(work_type_names, selected_work_types),
    )

    offset += limit

    urls = make_urls(
        offset=offset,
        query=query,
        selected_museums=selected_museums,
        selected_work_types=selected_work_types,
    )

    return {
        **search_results,
        "query": query,
        "offset": offset,
        "urls": urls,
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
        "museums": SUPPORTED_MUSEUMS,
    }


def build_search_context(params: SearchParams) -> dict[Any, Any]:
    """
    Build the full context for the search view.
    """
    filter_context = build_filter_context(params.request)
    main_context = build_main_context(params)
    return {
        **filter_context,
        **main_context,
        "example_queries": params.example_queries,
    }
