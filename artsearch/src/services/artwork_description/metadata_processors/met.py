"""MET (Metropolitan Museum of Art) metadata processor."""

import logging
from .base import remove_fields, remove_empty_fields

logger = logging.getLogger(__name__)

# Fields to exclude from MET metadata when generating descriptions
MET_FIELDS_TO_REMOVE = [
    "objectID",
    "accessionNumber",
    "isPublicDomain",
    "primaryImage",
    "primaryImageSmall",
    "additionalImages",
    "dimensions",
    "constituents",
    "constituentID",
    "department",
    "artistWikidata_URL",
    "artistULAN_URL",
    "measurements",
    "element_measurements",
    "creditLine",
    "objectURL",
    "tags",
    "AAT_URL",
    "Wikidata_URL",
    "objectWikidata_URL",
    "GalleryNumber",
    "rightsAndReproduction",
    "metadataDate",
    "linkResource",
    "isTimelineWork",
]


def clean_met_metadata(raw_data: dict) -> dict:
    """Clean and filter MET metadata for description generation.

    Args:
        raw_data: Raw JSON response from MET API

    Returns:
        Cleaned metadata dictionary with irrelevant fields removed
    """
    # MET API returns object directly (no wrapper)
    metadata = raw_data.copy()

    # Remove technical/irrelevant fields
    metadata = remove_fields(metadata, MET_FIELDS_TO_REMOVE)

    # Remove empty fields
    metadata = remove_empty_fields(metadata)

    logger.debug(f"Cleaned MET metadata: {list(metadata.keys())}")
    return metadata
