import logging
from typing import Optional
from artsearch.src.utils.get_museums import get_museum_slugs
from etl.pipeline.extract.factory import get_extractor

logger = logging.getLogger(__name__)


def run_extract(museum_slugs: Optional[list[str]] = None, force_refetch: bool = False) -> None:
    """
    Run extraction for specified museums or all museums.

    Args:
        museum_slugs: List of museum slugs to extract. If None, extracts all museums.
        force_refetch: Whether to force refetch all items regardless of existing data.
    """
    if museum_slugs is None:
        museum_slugs = get_museum_slugs()

    logger.info(f"Starting extraction for museums: {', '.join(museum_slugs)}")
    if force_refetch:
        logger.info("Force refetch enabled - will refetch all items regardless of existing data")

    for museum_slug in museum_slugs:
        logger.info(f"Starting extraction for {museum_slug.upper()}")

        extractor = get_extractor(museum_slug, force_refetch=force_refetch)
        if not extractor:
            logger.error(f"No extractor found for museum: {museum_slug}")
            continue

        try:
            extractor()
            logger.info(f"Extraction completed for {museum_slug.upper()}")
        except Exception as e:
            logger.error(f"Extraction failed for {museum_slug.upper()}: {e}")
            # Continue with other museums even if one fails
            continue

    logger.info("Extraction pipeline completed")


def extract_single_museum(museum_slug: str, force_refetch: bool = False) -> None:
    """
    Extract data for a single museum.

    Args:
        museum_slug: The museum slug to extract
        force_refetch: Whether to force refetch all items regardless of existing data
    """
    run_extract([museum_slug], force_refetch=force_refetch)
