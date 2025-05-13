from typing import Tuple
from artsearch.src.services.museum_clients.base_client import (
    MuseumAPIClientError,
    MuseumName,
)
from artsearch.src.services.museum_clients.factory import get_museum_client


def get_metadata_and_museum(
    object_number: str, museum_filter: MuseumName
) -> Tuple[str, MuseumName]:
    """
    Get metadata for a given object number without knowing the museum.
    This is slow (loops through museums), so only use it when necessary.
    If museum_filter is not "all", this is our best guess, so we start with it.

    Currently, this function only fetches the thumbnail URL, but it could be
    generalized to fetch all metadata if needed.

    This function will currently only be called, when user searches for items
    similar to item that is not already in the qdrant database.
    """
    if museum_filter != "all":
        museums: list[MuseumName] = [museum_filter, "smk", "cma"]
    else:
        museums: list[MuseumName] = ["smk", "cma"]

    for museum in museums:
        museum_client = get_museum_client(museum)
        try:
            thumbnail_url = museum_client.get_thumbnail_url(object_number)
            return thumbnail_url, museum
        except Exception:
            continue
    raise MuseumAPIClientError(
        f"No artwork found with inventory number: {object_number}"
    )
