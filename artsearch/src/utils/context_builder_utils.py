from urllib.parse import urlencode
from typing import Iterable, Literal
from django.http import HttpRequest
from django.urls import reverse
from artsearch.src.constants import WORK_TYPES_DICT


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
