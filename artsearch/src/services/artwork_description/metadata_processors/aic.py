"""AIC (Art Institute of Chicago) metadata processor."""

import logging
from .base import remove_fields, remove_empty_fields

logger = logging.getLogger(__name__)

# Fields to exclude from AIC metadata when generating descriptions
AIC_FIELDS_TO_REMOVE = [
    "id",
    "api_model",
    "api_link",
    "is_boosted",
    "thumbnail",
    "main_reference_number",
    "has_not_been_viewed_much",
    "boost_rank",
    "date_qualifier_title",
    "date_qualifier_id",
    "dimensions",
    "dimensions_details",
    "provenance_text",
    "publishing_verification_level",
    "internal_department_id",
    "fiscal_year",
    "fiscal_year_deaccession",
    "is_public_domain",
    "is_zoomable",
    "max_zoom_window_size",
    "copyright_notice",
    "has_multimedia_resources",
    "has_educational_resources",
    "has_advanced_imaging",
    "colorfulness",
    "color",
    "latitude",
    "longitude",
    "latlon",
    "is_on_view",
    "on_loan_display",
    "gallery_id",
    "nomisma_id",
    "artwork_type_id",
    "department_id",
    "artist_id",
    "artist_ids",
    "category_ids",
    "style_id",
    "alt_style_ids",
    "style_ids",
    "classification_id",
    "alt_classification_ids",
    "classification_ids",
    "subject_id",
    "alt_subject_ids",
    "subject_ids",
    "material_ids",
    "technique_id",
    "alt_technique_ids",
    "technique_ids",
    "image_id",
    "alt_image_ids",
    "document_ids",
    "sound_ids",
    "video_ids",
    "text_ids",
    "section_ids",
    "site_ids",
    "suggest_autocomplete_all",
    "source_updated_at",
    "updated_at",
    "timestamp",
    "info",
    "config",
    "material_id",
    "alt_material_ids",
]


def clean_aic_metadata(raw_data: dict) -> dict:
    """Clean and filter AIC metadata for description generation.

    Args:
        raw_data: Raw JSON response from AIC API

    Returns:
        Cleaned metadata dictionary with irrelevant fields removed
    """
    # AIC API returns data field
    if "data" in raw_data:
        metadata = raw_data["data"]
    else:
        metadata = raw_data

    # Remove technical/irrelevant fields
    metadata = remove_fields(metadata, AIC_FIELDS_TO_REMOVE)

    # Remove empty fields
    metadata = remove_empty_fields(metadata)

    logger.debug(f"Cleaned AIC metadata: {list(metadata.keys())}")
    return metadata
