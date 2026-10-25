from artsearch.models import RequestSource, SearchLog
from artsearch.src.services.museum_stats_service import get_work_type_names
from artsearch.src.utils.get_museums import get_museum_slugs
from artsearch.views.context_builders import (
    SearchParams,
    get_narrowing_filters,
)


def save_search_log(
    query: str,
    source: str,
    search_mode: str,
    museums: list[str],
    work_types: list[str],
    year_from: int | None,
    year_to: int | None,
    username: str | None = None,
) -> None:
    """
    Saves a search to the database. Filter lists should be empty when they
    cover everything.
    """
    SearchLog.objects.create(
        query=query,
        username=username,
        source=source,
        search_mode=search_mode,
        museums=museums,
        work_types=work_types,
        year_from=year_from,
        year_to=year_to,
    )


def log_search_query(params: SearchParams, image_search: bool = False) -> None:
    """
    Saves a website search, its mode and filters to the database.
    image_search marks a search by uploaded image that is actually being run.
    """
    if image_search:
        query, search_mode = "", SearchLog.SearchMode.UPLOAD
    elif params.query:
        query, search_mode = params.query, params.selected_search_mode
    else:
        return
    user = params.request.user
    try:
        museums, work_types = get_narrowing_filters(params)
        year_from, year_to = params.year_range
        save_search_log(
            query=query,
            source=RequestSource.WEB,
            search_mode=search_mode,
            museums=museums,
            work_types=work_types,
            year_from=year_from,
            year_to=year_to,
            username=user.username if user.is_authenticated else None,
        )
    except Exception as e:
        print(f"Error logging search query: {e}")


def log_api_search(query: str, params: dict, search_mode: str | None = None) -> None:
    """
    Saves a REST API search to the database. params is the dict from
    the API's _parse_search_params (None filters mean everything);
    search_mode overrides its mode (UPLOAD for image searches).
    """
    try:
        museums = params["museums"] or []
        if set(museums) >= set(get_museum_slugs()):
            museums = []
        work_types = params["work_types"] or []
        if set(work_types) >= set(get_work_type_names()):
            work_types = []
        save_search_log(
            query=query,
            source=RequestSource.API,
            search_mode=search_mode or params["search_mode"],
            museums=museums,
            work_types=work_types,
            year_from=params["year_from"],
            year_to=params["year_to"],
        )
    except Exception as e:
        print(f"Error logging API search query: {e}")
