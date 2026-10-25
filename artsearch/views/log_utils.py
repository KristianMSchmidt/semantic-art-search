from artsearch.models import SearchLog
from artsearch.views.context_builders import (
    SearchParams,
    get_narrowing_filters,
)


def log_search_query(params: SearchParams) -> None:
    """
    Saves the search query, its mode and filters to the database.
    """
    query = params.query
    if query:
        user = params.request.user
        username = user.username if user.is_authenticated else None
        try:
            museums, work_types = get_narrowing_filters(params)
            year_from, year_to = params.year_range
            SearchLog.objects.create(
                query=query,
                username=username,
                search_mode=params.selected_search_mode,
                museums=museums,
                work_types=work_types,
                year_from=year_from,
                year_to=year_to,
            )
        except Exception as e:
            print(f"Error logging search query: {e}")
