"""Finnish National Gallery (Kansallisgalleria) metadata processor."""

import logging
from .base import remove_empty_fields

logger = logging.getLogger(__name__)

# The museum's name for an unknown artist ("artist unknown"), not a real name
UNKNOWN_ARTIST_NAMES = {"tekijä ei tiedossa"}


def _english_names(items: list[dict] | None) -> list[str]:
    """English names of classifications/materials/keywords, falling back to Finnish."""
    names = []
    for item in items or []:
        name = (item.get("en") or item.get("fi") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _person(person: dict) -> dict:
    name = " ".join(p for p in (person.get("firstName"), person.get("familyName")) if p)
    if name.strip().lower() in UNKNOWN_ARTIST_NAMES:
        name = "unknown"
    return remove_empty_fields(
        {
            "name": name,
            "role": (person.get("role") or {}).get("en"),
            "attribution": (person.get("attribution") or {}).get("en"),
            "birth_year": person.get("birthYear"),
            "death_year": person.get("deathYear"),
            "birth_place": person.get("birthPlace"),
            "death_place": person.get("deathPlace"),
        }
    )


def clean_fng_metadata(raw_data: dict) -> dict:
    """Clean and filter Finnish National Gallery metadata for description generation.

    The raw objects are nested and multilingual (en/fi/sv), so this picks out the
    fields that describe the artwork rather than removing unwanted ones.

    Args:
        raw_data: Raw JSON stored during extraction (one object from the collection dump)

    Returns:
        Cleaned metadata dictionary
    """
    title = raw_data.get("title") or {}
    metadata = {
        "title": title.get("en"),
        "title_finnish": title.get("fi"),
        "title_swedish": title.get("sv"),
        "artists": [_person(p) for p in raw_data.get("people") or []],
        "date_prefix": (raw_data.get("datePrefix") or {}).get("en"),
        "year_from": raw_data.get("yearFrom"),
        "year_to": raw_data.get("yearTo"),
        "classifications": _english_names(raw_data.get("classifications")),
        "materials": _english_names(raw_data.get("materials")),
        "keywords": _english_names(raw_data.get("keywords")),
        "description": raw_data.get("description"),
        "collection": (raw_data.get("collection") or {}).get("en"),
        "museum": raw_data.get("responsibleOrganisation"),
        "acquisition_year": raw_data.get("acquisitionYear"),
    }
    metadata = remove_empty_fields(metadata)

    logger.debug(f"Cleaned FNG metadata: {list(metadata.keys())}")
    return metadata
