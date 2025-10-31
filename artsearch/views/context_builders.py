import json
from typing import Any, Iterable, Literal
from dataclasses import dataclass
from urllib.parse import urlencode

from django.http import HttpRequest
from django.urls import reverse

from artsearch.src.services.museum_stats_service import (
    get_work_type_names,
    aggregate_work_type_count_for_selected_museums,
    aggregate_museum_count_for_selected_work_types,
    get_total_works_for_filters,
)
from artsearch.src.services.search_service import handle_search
from artsearch.src.utils.get_museums import get_museum_slugs
from artsearch.src.constants.ui import EXAMPLE_QUERIES
from artsearch.src.constants.museums import SUPPORTED_MUSEUMS


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
    total_work_count: int


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
    Prepare (searchable) work types for the dropdown menu.
    """
    work_types_for_dropdown = []

    for searchable_work_type, count in work_types_count.items():
        eng_plural = searchable_work_type + "s"
        work_types_for_dropdown.append(
            {
                "value": searchable_work_type,
                "label": eng_plural,
                "count": count,
            }
        )
    return work_types_for_dropdown


def prepare_museums_for_dropdown(
    museum_counts: dict[str, int] | None = None,
    supported_museums: list[dict[str, str]] = SUPPORTED_MUSEUMS,
) -> list[dict[str, Any]]:
    """
    Prepare museums for the dropdown menu.
    Museums are sorted alphabetically by full_name.
    If museum_counts is provided, include count for each museum.
    """
    museums_for_dropdown = []

    # Sort museums alphabetically by full_name
    sorted_museums = sorted(supported_museums, key=lambda m: m["full_name"])

    for museum in sorted_museums:
        museum_slug = museum["slug"]
        museum_item: dict[str, Any] = {
            "value": museum_slug,
            "label": museum["full_name"],
            "short_label": museum["short_name"],
        }
        if museum_counts is not None:
            museum_item["count"] = museum_counts.get(museum_slug, 0)

        museums_for_dropdown.append(museum_item)

    return museums_for_dropdown


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

    total_works = get_total_works_for_filters(
        params.selected_museums,
        params.selected_work_types,
    )
    search_results = handle_search(
        query=params.query,
        offset=offset,
        limit=limit,
        museum_prefilter=museum_prefilter,
        work_type_prefilter=work_type_prefilter,
        total_works=total_works,
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
        "total_works": total_works,
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
    work_type_total = work_type_summary.total

    museum_summary = aggregate_museum_count_for_selected_work_types(
        tuple(selected_work_types)
    )
    museum_total = museum_summary.total

    prepared_work_types = prepare_work_types_for_dropdown(work_type_summary.work_types)
    prepared_museums = prepare_museums_for_dropdown(museum_summary.work_types)

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
            total_work_count=work_type_total,
            all_items_json=json.dumps(work_type_names),
            selected_items_json=json.dumps(selected_work_types),
            label_name="Work Type",
        ),
        "museum_filter_context": FilterContext(
            dropdown_name="museums",
            initial_button_label=initial_museums_label,
            dropdown_items=prepared_museums,
            selected_items=selected_museums,
            total_work_count=museum_total,
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
