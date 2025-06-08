from artsearch.models import SearchLog
from artsearch.src.context_builders import (
    SearchParams,
)

def log_search_query(params: SearchParams) -> None:
    """
    Saves the search query to the database.
    """
    query = params.query
    if query:
        user = params.request.user
        username = user.username if user.is_authenticated else None
        try:
            SearchLog.objects.create(query=query, username=username)
        except Exception as e:
            print(f"Error logging search query: {e}")
