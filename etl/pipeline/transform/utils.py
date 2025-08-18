import re
from typing import Any
from artsearch.src.constants import WORK_TYPES_DICT, SEARCHABLE_WORK_TYPES


def get_searchable_work_types(work_types: list[str]) -> list[str]:
    """
    Given a list of original work types (not necessarily in English) for a given artwork,
    return a list of standardized searchable work types in English.

    Returns empty list if no searchable work types found (to handle gracefully).
    """
    searchable_work_types = set()
    for work_type in work_types:
        if work_type in WORK_TYPES_DICT:
            work_type_eng = WORK_TYPES_DICT[work_type]["eng_sing"]
            if work_type_eng in SEARCHABLE_WORK_TYPES:
                searchable_work_types.add(work_type_eng)
            for category in SEARCHABLE_WORK_TYPES:
                if category in work_type_eng:
                    searchable_work_types.add(category)
    return list(searchable_work_types)


def safe_int_from_date(date_str: str) -> int | None:
    """
    Extract year as integer from date string, handling various formats gracefully.

    Examples:
    - "1650-01-01" -> 1650
    - "1650" -> 1650
    - "ca. 1650" -> 1650
    - "invalid" -> None
    """
    if not date_str:
        return None

    # Extract first 4-digit number from string
    match = re.search(r"\d{4}", str(date_str))
    if match:
        try:
            return int(match.group())
        except ValueError:
            pass
    return None


def extract_primary_title(titles: list[dict]) -> str | None:
    """
    Extract the primary title from various title structures.

    Handles SMK-style title lists with language/type specifications.
    """
    if not titles or not isinstance(titles, list):
        return None

    # Try to find primary title (usually first one or one marked as primary)
    for title_obj in titles:
        if isinstance(title_obj, dict):
            # SMK format: {"title": "Title text", "language": "da", "type": "main"}
            if title_obj.get("title"):
                return title_obj["title"]
        elif isinstance(title_obj, str):
            # Simple string format
            return title_obj

    return None


def extract_artist_names(artists: list[Any]) -> list[str]:
    """
    Extract artist names from various artist data structures.

    Handles both simple strings and complex objects with name fields.
    """
    if not artists or not isinstance(artists, list):
        return []

    names = []
    for artist in artists:
        if isinstance(artist, str):
            names.append(artist)
        elif isinstance(artist, dict):
            # Try common name fields
            name = (
                artist.get("name") or artist.get("title") or artist.get("artist_name")
            )
            if name:
                names.append(name)

    return names
