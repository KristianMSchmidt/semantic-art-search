"""Museum metadata fetching and processing."""

from typing import Any
import requests
import xmltodict
from artsearch.src.services.museum_clients.utils import get_museum_api_url
from .metadata_processors import (
    clean_smk_metadata,
    clean_cma_metadata,
    clean_met_metadata,
    clean_rma_metadata,
    clean_aic_metadata,
)


# Timeout for museum API requests (seconds)
API_TIMEOUT = 10


def fetch_and_clean_metadata(
    museum_slug: str,
    object_number: str,
    museum_db_id: str,
) -> dict[str, Any]:
    """Fetch and clean metadata from museum API.

    Args:
        museum_slug: Museum identifier (e.g., 'smk', 'met')
        object_number: Artwork object number
        museum_db_id: Museum's internal database ID

    Returns:
        Cleaned metadata dictionary

    Raises:
        ValueError: If museum is unsupported or API request fails
    """
    # Get API URL for this museum/artwork
    api_url = get_museum_api_url(museum_slug, object_number, museum_db_id)
    if not api_url:
        raise ValueError(f"Unsupported museum: {museum_slug}")

    # Fetch raw data
    try:
        response = requests.get(api_url, timeout=API_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch metadata from museum API: {str(e)}")

    # Parse response based on content type
    content_type = response.headers.get("Content-Type", "")

    if "xml" in content_type.lower() or museum_slug == "rma":
        # XML response (RMA uses XML)
        raw_data = xmltodict.parse(response.content)
        metadata = _clean_xml_metadata(museum_slug, raw_data)
    else:
        # JSON response (SMK, CMA, MET, AIC)
        raw_data = response.json()
        metadata = _clean_json_metadata(museum_slug, raw_data)

    return metadata


def _clean_json_metadata(museum_slug: str, raw_data: dict) -> dict[str, Any]:
    """Clean JSON metadata based on museum.

    Args:
        museum_slug: Museum identifier
        raw_data: Raw JSON response from museum API

    Returns:
        Cleaned metadata dictionary

    Raises:
        ValueError: If museum slug is unknown
    """
    if museum_slug == "smk":
        return clean_smk_metadata(raw_data)
    elif museum_slug == "cma":
        return clean_cma_metadata(raw_data)
    elif museum_slug == "met":
        return clean_met_metadata(raw_data)
    elif museum_slug == "aic":
        return clean_aic_metadata(raw_data)
    else:
        raise ValueError(f"Unknown museum slug for JSON cleaning: {museum_slug}")


def _clean_xml_metadata(museum_slug: str, raw_data: dict) -> dict[str, Any]:
    """Clean XML metadata based on museum.

    Args:
        museum_slug: Museum identifier
        raw_data: Parsed XML (via xmltodict) from museum API

    Returns:
        Cleaned metadata dictionary

    Raises:
        ValueError: If museum slug is unknown
    """
    if museum_slug == "rma":
        return clean_rma_metadata(raw_data)
    else:
        raise ValueError(f"Unknown museum slug for XML cleaning: {museum_slug}")
