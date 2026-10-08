"""NGA (National Gallery of Art) metadata processor."""

import logging
from .base import remove_fields, remove_empty_fields

logger = logging.getLogger(__name__)

# Fields to exclude from NGA metadata when generating descriptions
NGA_FIELDS_TO_REMOVE = [
    "objectid",
    "uuid",
    "accessioned",
    "accessionnum",
    "locationid",
    "visualbrowsertimespan",
    "visualbrowserclassification",
    "dimensions",
    "provenancetext",
    "parentid",
    "isvirtual",
    "departmentabbr",
    "lastdetectedmodification",
    "wikidataid",
    "customprinturl",
    "image",
]


def clean_nga_metadata(raw_data: dict) -> dict:
    """Clean and filter NGA metadata for description generation.

    Args:
        raw_data: Raw JSON stored during extraction (objects.csv row + image row)

    Returns:
        Cleaned metadata dictionary with irrelevant fields removed
    """
    # Keep NGA's image description (alt text), which describes the depicted content
    assistive_text = raw_data.get("image", {}).get("assistivetext")

    metadata = remove_fields(raw_data, NGA_FIELDS_TO_REMOVE)
    if assistive_text:
        metadata["image_description"] = assistive_text

    metadata = remove_empty_fields(metadata)

    logger.debug(f"Cleaned NGA metadata: {list(metadata.keys())}")
    return metadata
