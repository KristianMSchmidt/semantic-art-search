"""CMA (Cleveland Museum of Art) metadata processor."""

import logging
from .base import remove_fields, remove_empty_fields

logger = logging.getLogger(__name__)

# Fields to exclude from CMA metadata when generating descriptions
CMA_FIELDS_TO_REMOVE = [
    "id",
    "accession_number",
    "share_license_status",
    "current_location",
    "dimensions",
    "copyright",
    "provenance",
    "related_works",
    "former_accession_numbers",
    "external_resources",
    "url",
    "images",
    "citations",
    "credit_line",
    "exhibitions",
    "alternate_images",
    "sketchfab_id",
    "sketchfab_url",
    "legal_status",
    "athena_id",
    "accession_date",
    "sortable_date",
    "measurements",
    "on_loan",
    "recently_acquired",
    "conservation_statement",
    "has_conservation_images",
    "cover_accession_number",
    "is_nazi_era_provenance",
    "impression",
    "updated_at",
    "collapse_artists",
]


def clean_cma_metadata(raw_data: dict) -> dict:
    """Clean and filter CMA metadata for description generation.

    Args:
        raw_data: Raw JSON response from CMA API

    Returns:
        Cleaned metadata dictionary with irrelevant fields removed
    """
    # CMA API returns data array
    if "data" in raw_data and len(raw_data["data"]) > 0:
        metadata = raw_data["data"][0]
    else:
        logger.warning("CMA API response missing 'data' array")
        metadata = raw_data

    # Remove technical/irrelevant fields
    metadata = remove_fields(metadata, CMA_FIELDS_TO_REMOVE)

    # Remove empty fields
    metadata = remove_empty_fields(metadata)

    logger.debug(f"Cleaned CMA metadata: {list(metadata.keys())}")
    return metadata
