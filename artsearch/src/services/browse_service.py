"""
Service for browsing artworks with random ordering and pagination.

Uses PostgreSQL for deterministic random ordering (via seed) and pagination,
then fetches full payloads from Qdrant for display.

The website's default view (no filters) only shows colourful artworks: most
of the collection is monochrome prints and drawings, which made the home page
look bland. Any filter browses the whole collection again; the API's random
endpoint always does.
"""

from __future__ import annotations

import time
import logging
from typing import TYPE_CHECKING

from django.db.models import Q
from django.db.models.expressions import RawSQL

from artsearch.models import ArtworkStats
from artsearch.src.services.museum_stats_service import filter_by_year_range
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.config import config

if TYPE_CHECKING:
    from artsearch.src.services.search_service import SearchResult

logger = logging.getLogger(__name__)

# Minimum ArtworkStats.colorfulness for the default view (~top 15-20% of the
# collection; see etl/services/colorfulness_service.py for the scale)
DEFAULT_VIEW_MIN_COLORFULNESS = 20.0



def default_view_artworks(min_colorfulness: float) -> Q:
    """
    Artworks for the default view: at least this colourful, plus those not
    scored yet (so an unscored database, or a half-finished
    compute_colorfulness run, still shows everything not yet known to be
    monochrome), minus those excluded from it (tobacco trade cards).
    """
    colorful = Q(colorfulness__gte=min_colorfulness) | Q(
        colorfulness__isnull=True
    )
    return colorful & Q(excluded_from_default_view=False)


def get_random_artwork_ids(
    museums: list[str] | None,
    work_types: list[str] | None,
    seed: str,
    limit: int,
    offset: int,
    year_from: int | None = None,
    year_to: int | None = None,
    min_colorfulness: float | None = None,
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
        year_from: Earliest production year, or None for no lower bound
        year_to: Latest production year, or None for no upper bound
        min_colorfulness: Only default view artworks (see
            default_view_artworks) this colourful, or None for all

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

    queryset = filter_by_year_range(queryset, year_from, year_to)

    if min_colorfulness is not None:
        queryset = queryset.filter(default_view_artworks(min_colorfulness))

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
        f"years={year_from}-{year_to}, min_colorfulness={min_colorfulness}, "
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
    year_from: int | None = None,
    year_to: int | None = None,
    colorful_default_view: bool = False,
) -> SearchResult:
    """
    Handle browsing (no query) with proper pagination.

    Fetches random artwork IDs from PostgreSQL, then retrieves full payloads
    from Qdrant for display.

    With colorful_default_view and no filters, only colourful artworks are
    shown and counted.
    """
    start_time = time.time()

    min_colorfulness = None
    is_unfiltered = all(
        f is None for f in (museum_prefilter, work_type_prefilter, year_from, year_to)
    )
    if colorful_default_view and is_unfiltered:
        min_colorfulness = DEFAULT_VIEW_MIN_COLORFULNESS
        total_works = ArtworkStats.objects.filter(
            default_view_artworks(min_colorfulness)
        ).count()

    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    # Get random IDs from PostgreSQL
    artwork_ids = get_random_artwork_ids(
        museums=museum_prefilter,
        work_types=work_type_prefilter,
        seed=seed,
        limit=limit,
        offset=offset,
        year_from=year_from,
        year_to=year_to,
        min_colorfulness=min_colorfulness,
    )

    # Fetch full payloads from Qdrant
    results = qdrant_service.get_items_by_ids(artwork_ids) if artwork_ids else []

    # Header text - only show for search results, not initial load
    if is_initial_load:
        header_text = ""
    else:
        header_text = f"Search results ({total_works} works)"

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
        "total_works": total_works,
    }
