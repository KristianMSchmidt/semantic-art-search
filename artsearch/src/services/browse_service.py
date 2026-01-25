"""
Service for browsing artworks with random ordering and pagination.

Uses PostgreSQL for deterministic random ordering (via seed) and pagination,
then fetches full payloads from Qdrant for display.
"""

import time
import logging
from typing import Any

from django.db.models.expressions import RawSQL

from artsearch.models import ArtworkStats
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.config import config

logger = logging.getLogger(__name__)


def get_random_artwork_ids(
    museums: list[str] | None,
    work_types: list[str] | None,
    seed: str,
    limit: int,
    offset: int,
) -> list[tuple[str, str]]:
    """
    Get random artwork IDs from PostgreSQL with deterministic ordering.

    Uses md5 hash of (museum_slug || object_number || seed) for deterministic
    random ordering. Same seed always produces same order.

    Args:
        museums: List of museum slugs to filter by, or None for all
        work_types: List of work types to filter by, or None for all
        seed: Random seed for deterministic ordering
        limit: Number of results to return
        offset: Number of results to skip

    Returns:
        List of (museum_slug, object_number) tuples
    """
    start_time = time.time()

    queryset = ArtworkStats.objects.all()

    # Apply museum filter if specified
    if museums is not None:
        queryset = queryset.filter(museum_slug__in=museums)

    # Apply work type filter using ?| operator (same pattern as museum_stats_service)
    if work_types is not None:
        queryset = queryset.extra(
            where=["searchable_work_types ?| %s"], params=[work_types]
        )

    # Deterministic random order using md5 hash with seed
    queryset = queryset.order_by(
        RawSQL("md5(museum_slug || object_number || %s)", [seed])
    )

    # Pagination via slicing
    queryset = queryset[offset : offset + limit]

    result = [(row.museum_slug, row.object_number) for row in queryset]

    elapsed = (time.time() - start_time) * 1000
    logger.info(
        f"[TIMING] get_random_artwork_ids - "
        f"museums={museums}, work_types={work_types}, "
        f"offset={offset}, limit={limit}: {elapsed:.2f}ms"
    )

    return result


def handle_browse(
    offset: int,
    limit: int,
    museum_prefilter: list[str] | None,
    work_type_prefilter: list[str] | None,
    seed: str,
    total_works: int,
    is_initial_load: bool,
) -> dict[str, Any]:
    """
    Handle browsing (no query) with proper pagination.

    Fetches random artwork IDs from PostgreSQL, then retrieves full payloads
    from Qdrant for display.

    Args:
        offset: Number of results to skip
        limit: Number of results to return
        museum_prefilter: Museum filter or None for all
        work_type_prefilter: Work type filter or None for all
        seed: Random seed for deterministic ordering
        total_works: Total count of matching artworks (for header)
        is_initial_load: True if this is the initial page load (query=None)

    Returns:
        Dict with results, header_text, error_message, error_type
    """
    start_time = time.time()
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    # Get random IDs from PostgreSQL
    artwork_ids = get_random_artwork_ids(
        museums=museum_prefilter,
        work_types=work_type_prefilter,
        seed=seed,
        limit=limit,
        offset=offset,
    )

    # Fetch full payloads from Qdrant
    results = qdrant_service.get_items_by_ids(artwork_ids) if artwork_ids else []

    # Header text - only show for search results, not initial load
    if is_initial_load:
        header_text = ""
    else:
        header_text = f"Search results ({total_works})"

    elapsed = (time.time() - start_time) * 1000
    logger.info(
        f"[TIMING] handle_browse - total: {elapsed:.2f}ms, "
        f"results={len(results)}, offset={offset}"
    )

    return {
        "results": results,
        "header_text": header_text,
        "error_message": None,
        "error_type": None,
    }
