"""Helper utilities for museum clients."""

from artsearch.src.services.museum_clients.factory import get_museum_client


def get_museum_api_url(
    museum_slug: str, object_number: str, museum_db_id: str
) -> str | None:
    """Returns the URL to the artwork's API endpoint at the source museum."""
    museum_api_client = get_museum_client(museum_slug)
    if museum_slug in ("met", "rma", "aic"):
        return museum_api_client.get_object_url(museum_db_id)
    else:
        return museum_api_client.get_object_url(object_number)


def get_museum_page_url(
    museum_slug: str, object_number: str, museum_db_id: str
) -> str | None:
    """Returns the URL to the artwork's public page at the source museum."""
    museum_api_client = get_museum_client(museum_slug)
    if museum_slug in ("met", "aic"):
        return museum_api_client.get_page_url(museum_db_id)
    else:
        return museum_api_client.get_page_url(object_number)
