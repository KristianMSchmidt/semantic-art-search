import random
from artsearch.src.utils.constants import EXAMPLE_TEXT_QUERIES
from artsearch.src.services.search_service import search_service

def get_valid_limit(limit: str | None, default: int = 10) -> int:
    """Safely converts a limit to an integer, ensuring it is between 5 and 30."""
    try:
        return max(5, min(50, int(limit)))  # Clamp between 5 and 50
    except (ValueError, TypeError):
        return default


def get_default_text_query(user_query: str | None) -> str:
    """Returns the user query if provided, otherwise selects a random example query."""
    return user_query if user_query and user_query.strip() else random.choice(EXAMPLE_TEXT_QUERIES)


def get_object_number(user_query: str | None) -> str:
    """Returns the user query if provided, otherwise selects a random example query."""

    if user_query is None:
        return search_service.get_random_point()['object_number']

    return user_query.strip()
