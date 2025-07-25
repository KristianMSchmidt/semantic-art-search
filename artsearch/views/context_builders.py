import json
from typing import Any, Iterable, Literal
from dataclasses import dataclass
from urllib.parse import urlencode

from django.http import HttpRequest
from django.urls import reverse

from artsearch.src.services.museum_stats_service import (
    get_work_type_names,
    aggregate_work_type_count_for_selected_museums,
)
from artsearch.src.services.search_service import handle_search
from artsearch.src.utils.get_museums import get_museum_slugs
from artsearch.src.constants import EXAMPLE_QUERIES, SUPPORTED_MUSEUMS, WORK_TYPES_DICT


RESULTS_PER_PAGE = 20


@dataclass
class SearchParams:
    request: HttpRequest
    limit: int = RESULTS_PER_PAGE

    @property
    def query(self) -> str | None:
        return retrieve_query(self.request)

    @property
    def selected_museums(self) -> list[str]:
        museum_names = get_museum_slugs()
        return retrieve_selected(museum_names, self.request, "museums")

    @property
    def selected_work_types(self) -> list[str]:
        work_type_names = get_work_type_names()
        return retrieve_selected(work_type_names, self.request, "work_types")

    @property
    def offset(self) -> int:
        return retrieve_offset(self.request)


@dataclass
class FilterContext:
    dropdown_name: str
    initial_button_label: str
    dropdown_items: list[dict[str, Any]]
    selected_items: list[str]
    label_name: str
    all_items_json: str
    selected_items_json: str
    total_work_count: int | None = None


def retrieve_query(request: HttpRequest) -> str | None:
    query = request.GET.get("query")
    if query is None:
        return None
    return query.strip()


def retrieve_offset(request: HttpRequest) -> int:
    offset = request.GET.get("offset", None)
    if offset is None:
        return 0
    return int(offset)


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
) -> list[dict[str, Any]]:
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
                "value": work_type,
                "label": eng_plural,
                "count": count,
            }
        )
    return work_types_for_dropdown


def prepare_museums_for_dropdown(
    supported_museums: list[dict[str, str]] = SUPPORTED_MUSEUMS,
) -> list[dict[str, str]]:
    return [
        {"value": museum["slug"], "label": museum["full_name"]}
        for museum in supported_museums
    ]


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


def make_url_with_params(
    url_name: str,
    query: str | None = None,
    offset: int | None = None,
    selected_work_types: list[str] = [],
    selected_museums: list[str] = [],
) -> str:
    """Make a URL with query parameters for pagination and filtering."""
    query_params = {}
    if offset is not None:
        query_params["offset"] = offset
    if query:
        query_params["query"] = query
    if selected_work_types:
        query_params["work_types"] = selected_work_types
    if selected_museums:
        query_params["museums"] = selected_museums
    if not query_params:
        return reverse(url_name)
    return f"{reverse(url_name)}?{urlencode(query_params, doseq=True)}"


def make_urls_with_params(
    query: str | None,
    offset: int,
    selected_work_types: list[str],
    selected_museums: list[str],
) -> dict[str, str]:
    """Make URLs with query parameters for pagination and filtering"""
    return {
        "get_artworks_with_params": make_url_with_params(
            url_name="get-artworks",
            query=query,
            offset=offset,
            selected_work_types=selected_work_types,
            selected_museums=selected_museums,
        ),
    }


def works_matching_filters(params: SearchParams) -> bool:
    """Check if there are any works matching the selected filters."""

    work_type_count = aggregate_work_type_count_for_selected_museums(
        params.selected_museums
    ).work_types

    for work_type in params.selected_work_types:
        if work_type_count.get(work_type, 0) > 0:
            return True
    return False


def build_search_context(params: SearchParams) -> dict[str, Any]:
    """
    Build the main context for the search view.
    """
    offset = params.offset
    limit = params.limit

    museum_prefilter = make_prefilter(get_museum_slugs(), params.selected_museums)
    work_type_prefilter = make_prefilter(
        get_work_type_names(), params.selected_work_types
    )

    search_results = handle_search(
        query=params.query,
        offset=offset,
        limit=limit,
        museum_prefilter=museum_prefilter,
        work_type_prefilter=work_type_prefilter,
    )

    urls = make_urls_with_params(
        query=params.query,
        offset=offset + limit,
        selected_museums=params.selected_museums,
        selected_work_types=params.selected_work_types,
    )

    return {
        **search_results,
        "query": params.query,
        "is_first_batch": offset == 0,
        "works_matching_filters": works_matching_filters(params),
        "urls": urls,
    }


def build_filter_contexts(params: SearchParams) -> dict[str, FilterContext]:
    """
    Build the template context for search and dropdown templates
    The 'initial labels' are only used for the search template, the rest is used for both.
    """
    museum_names = get_museum_slugs()
    work_type_names = get_work_type_names()

    selected_museums = params.selected_museums
    selected_work_types = params.selected_work_types

    work_type_summary = aggregate_work_type_count_for_selected_museums(selected_museums)
    total_work_count = work_type_summary.total

    prepared_work_types = prepare_work_types_for_dropdown(work_type_summary.work_types)
    prepared_museums = prepare_museums_for_dropdown()

    initial_work_types_label = prepare_initial_label(
        selected_work_types, work_type_names, "work_types"
    )
    initial_museums_label = prepare_initial_label(
        selected_museums, museum_names, "museums"
    )

    return {
        "work_type_filter_context": FilterContext(
            dropdown_name="work_types",
            initial_button_label=initial_work_types_label,
            dropdown_items=prepared_work_types,
            selected_items=selected_work_types,
            total_work_count=total_work_count,
            all_items_json=json.dumps(work_type_names),
            selected_items_json=json.dumps(selected_work_types),
            label_name="Work Type",
        ),
        "museum_filter_context": FilterContext(
            dropdown_name="museums",
            initial_button_label=initial_museums_label,
            dropdown_items=prepared_museums,
            selected_items=selected_museums,
            all_items_json=json.dumps(museum_names),
            selected_items_json=json.dumps(selected_museums),
            label_name="Museum",
        ),
    }


def build_home_context(
    params: SearchParams, example_queries: list[str] = EXAMPLE_QUERIES["chosen"]
) -> dict[str, Any]:
    """
    Build the full context for the search view.
    """
    filter_contexts = build_filter_contexts(params)
    return {
        **filter_contexts,
        "example_queries": example_queries,
    }
