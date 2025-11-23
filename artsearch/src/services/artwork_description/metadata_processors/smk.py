"""SMK (Statens Museum for Kunst) metadata processor."""

import logging
from .base import remove_fields, remove_empty_fields

logger = logging.getLogger(__name__)

# Fields to exclude from SMK metadata when generating descriptions
SMK_FIELDS_TO_REMOVE = [
    "id",
    "created",
    "modified",
    "number_of_parts",
    "acquisition_date",
    "acquisition_date_precision",
    "dimensions",
    "part_of",
    "has_text",
    "object_number",
    "object_url",
    "frontend_url",
    "iiif_manifest",
    "enrichment_url",
    "similar_images_url",
    "production_dates_notes",
    "public_domain",
    "rights",
    "on_display",
    "alternative_images",
    "image_mime_type",
    "image_iiif_id",
    "image_iiif_info",
    "image_width",
    "image_height",
    "image_size",
    "image_thumbnail",
    "image_native",
    "image_cropped",
    "image_orientation",
    "image_hq",
    "has_3d_file",
    "has_image",
    "colors",
    "suggested_bg_color",
    "entropy",
    "contrast",
    "saturation",
    "colortemp",
    "brightness",
]


def clean_smk_metadata(raw_data: dict) -> dict:
    """Clean and filter SMK metadata for description generation.

    Args:
        raw_data: Raw JSON response from SMK API

    Returns:
        Cleaned metadata dictionary with irrelevant fields removed
    """
    # SMK API returns items array
    if "items" in raw_data and len(raw_data["items"]) > 0:
        metadata = raw_data["items"][0]
    else:
        logger.warning("SMK API response missing 'items' array")
        metadata = raw_data

    # Remove technical/irrelevant fields
    metadata = remove_fields(metadata, SMK_FIELDS_TO_REMOVE)

    # Remove empty fields
    metadata = remove_empty_fields(metadata)

    logger.debug(f"Cleaned SMK metadata: {list(metadata.keys())}")
    return metadata
