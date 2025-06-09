from urllib.parse import urlencode
from typing import Iterable, Literal, Any
from django.http import HttpRequest
from django.urls import reverse
from artsearch.src.constants import WORK_TYPES_DICT, SUPPORTED_MUSEUMS


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


def make_url(
    url_name: str,
    offset: int | None = None,
    query: str | None = None,
    selected_work_types: list[str] = [],
    selected_museums: list[str] = [],
) -> str:
    """Make urls with query parameters."""
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


def make_urls(
    offset: int,
    query: str | None,
    selected_work_types: list[str],
    selected_museums: list[str],
) -> dict[str, str]:
    return {
        "get_artworks_with_params": make_url(
            "get-artworks",
            offset,
            query,
            selected_work_types,
            selected_museums,
        ),
    }
