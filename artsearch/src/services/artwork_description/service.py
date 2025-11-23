"""Main service orchestrator for artwork description generation."""

import logging
from etl.services.bucket_service import get_bucket_image_url
from .cache import get_cached_description, save_to_cache
from .metadata_fetcher import fetch_and_clean_metadata
from .openai_client import generate_with_openai

logger = logging.getLogger(__name__)


def generate_description(
    museum_slug: str,
    object_number: str,
    museum_db_id: str,
    force_regenerate: bool = False,
) -> str | None:
    """Generate an AI-powered artwork description using OpenAI GPT-4o vision.

    Uses database caching to avoid redundant API calls.

    Args:
        museum_slug: Museum identifier (e.g., 'smk', 'met')
        object_number: Artwork object number
        museum_db_id: Museum's internal database ID
        force_regenerate: If True, bypass cache and generate fresh description

    Returns:
        Generated description string, or None if generation fails
    """
    # Check cache first (unless force regenerate)
    if not force_regenerate:
        cached = get_cached_description(museum_slug, object_number)
        if cached:
            return cached

    # Generate new description
    try:
        # Fetch and clean metadata
        metadata = fetch_and_clean_metadata(museum_slug, object_number, museum_db_id)
        metadata_str = str(metadata)

        # Get image URL from S3 bucket
        image_url = get_bucket_image_url(
            museum=museum_slug,
            object_number=object_number,
            use_etl_bucket=False,  # Use app/production bucket
        )

        # Generate description with OpenAI
        description = generate_with_openai(metadata_str, image_url)

        # Save to cache
        save_to_cache(museum_slug, object_number, description)

        return description

    except Exception as e:
        # Log detailed error internally for debugging
        logger.error(
            f"Failed to generate description for {museum_slug}:{object_number}: {str(e)}",
            exc_info=True
        )
        # Return None on error (view/template handles user messaging)
        return None
