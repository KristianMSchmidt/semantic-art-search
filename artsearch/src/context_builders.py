from dataclasses import dataclass
import json
from typing import Any
from django.http import HttpRequest
from artsearch.src.services.museum_stats_service import (
    get_work_type_names,
    aggregate_work_type_count_for_selected_museums,
)
from artsearch.src.services.search_service import handle_search
from artsearch.src.utils.get_museums import get_museum_names
from artsearch.src.utils.context_builder_utils import (
    retrieve_selected,
    retrieve_query,
    retrieve_offset,
    prepare_work_types_for_dropdown,
    prepare_museums_for_dropdown,
    prepare_initial_label,
    make_prefilter,
    make_urls,
)
from artsearch.src.constants import EXAMPLE_QUERIES


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
        museum_names = get_museum_names()
        return retrieve_selected(museum_names, self.request, "museums")

    @property
    def selected_work_types(self) -> list[str]:
        work_type_names = get_work_type_names()
        return retrieve_selected(work_type_names, self.request, "work_types")

    @property
    def offset(self) -> int:
        return retrieve_offset(self.request)


def build_main_context(params: SearchParams) -> dict[str, Any]:
    """
    Build the main context for the search view.
    """
    offset = params.offset
    limit = params.limit

    museum_prefilter = make_prefilter(get_museum_names(), params.selected_museums)
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

    offset += limit

    urls = make_urls(
        offset=offset,
        query=params.query,
        selected_museums=params.selected_museums,
        selected_work_types=params.selected_work_types,
    )

    return {
        **search_results,
        "query": params.query,
        "offset": offset,
        "urls": urls,
    }


def build_filter_contexts(params: SearchParams) -> dict[str, Any]:
    """
    Build the template context for search and dropdown templates
    The 'initial labels' are only used for the search template, the rest is used for both.
    """
    museum_names = get_museum_names()
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
        "work_type_filter_context": {
            "dropdown_name": "work_types",
            "initial_button_label": initial_work_types_label,
            "dropdown_items": prepared_work_types,
            "selected_items": selected_work_types,
            "total_work_count": total_work_count,
            "all_items_json": json.dumps(work_type_names), 
            "selected_items_json": json.dumps(selected_work_types),
            "label_name": "Work Type"
        },
        "museum_filter_context": {
            "dropdown_name": "museums",
            "initial_button_label": initial_museums_label,
            "dropdown_items": prepared_museums,
            "selected_items": selected_museums,
            "all_items_json": json.dumps(museum_names), 
            "selected_items_json": json.dumps(selected_museums),  
            "label_name": "Museum",
        }
    }


def build_search_context(
    params: SearchParams, example_queries: list[str] = EXAMPLE_QUERIES["chosen"]
) -> dict[str, Any]:
    """
    Build the full context for the search view.
    """
    filter_contexts = build_filter_contexts(params)
    main_context = build_main_context(params)
    return {
        **filter_contexts,
        **main_context,
        "example_queries": example_queries,
    }
