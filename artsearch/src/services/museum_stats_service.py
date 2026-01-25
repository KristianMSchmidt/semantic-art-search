"""
Service to aggregate artwork statistics per museum and work type.
Correctly handles artworks with multiple work types (no double-counting)
LRU cache can be reset using /clear-cache/ endpoint.
"""

import time
import logging
from functools import lru_cache
from dataclasses import dataclass
from django.db import connection
from django.db.models import Count
from artsearch.models import ArtworkStats
from artsearch.src.cache_registry import register_cache

logger = logging.getLogger(__name__)


@dataclass
class MuseumWorkTypeSummary:
    """
    Summary of work type/museum counts.
    work_types: dict mapping work_type/museum to count
    total: total unique artworks matching filters
    """

    work_types: dict[str, int]
    total: int


@register_cache
@lru_cache(maxsize=32)
def aggregate_work_type_count_for_selected_museums(
    selected_museums: tuple[str],
) -> MuseumWorkTypeSummary:
    """
    Aggregates work type counts and total work count for the given museums.
    Used every time the work type filter dropdown is created or updated (based on selected museums).

    Args:
        selected_museums: Tuple of museum slugs to filter by (must be tuple for caching)

    Returns:
        MuseumWorkTypeSummary with work_types dict and total count
    """
    start_time = time.time()
    logger.info(
        f"[CACHE] aggregate_work_type_count called with museums: {selected_museums}"
    )

    # Use PostgreSQL's jsonb_array_elements_text to unnest work types at database level
    # This is 100x faster than fetching all rows and looping in Python
    query_start = time.time()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                work_type,
                COUNT(*) as count
            FROM
                artsearch_artworkstats,
                jsonb_array_elements_text(searchable_work_types) as work_type
            WHERE
                museum_slug = ANY(%s)
            GROUP BY work_type
            ORDER BY count DESC
            """,
            [[museum for museum in selected_museums]],
        )

        work_type_counts = {row[0]: row[1] for row in cursor.fetchall()}
    logger.info(
        f"[TIMING] aggregate_work_type_count - Database GROUP BY: {(time.time() - query_start) * 1000:.2f}ms"
    )

    # Ensure all known work types are included (even with 0 count)
    get_names_start = time.time()
    all_work_types = get_work_type_names()
    logger.info(
        f"[TIMING] aggregate_work_type_count - get_work_type_names: {(time.time() - get_names_start) * 1000:.2f}ms"
    )

    for work_type in all_work_types:
        if work_type not in work_type_counts:
            work_type_counts[work_type] = 0

    # Sort by count descending
    sorted_work_types = dict(
        sorted(work_type_counts.items(), key=lambda x: x[1], reverse=True)
    )

    # Total unique artworks
    count_start = time.time()
    total = ArtworkStats.objects.filter(museum_slug__in=selected_museums).count()
    logger.info(
        f"[TIMING] aggregate_work_type_count - COUNT query: {(time.time() - count_start) * 1000:.2f}ms"
    )

    elapsed = (time.time() - start_time) * 1000
    logger.info(
        f"[TIMING] aggregate_work_type_count_for_selected_museums - TOTAL: {elapsed:.2f}ms"
    )

    return MuseumWorkTypeSummary(work_types=sorted_work_types, total=total)


@register_cache
@lru_cache(maxsize=256)
def aggregate_museum_count_for_selected_work_types(
    selected_work_types: tuple[str],
) -> MuseumWorkTypeSummary:
    """
    Aggregates museum counts and total work count for the given work types.
    Returns counts per museum based on selected work types.
    Correctly counts unique artworks (avoids double-counting artworks with multiple work types).

    Used every time the museum filter dropdown is created or updated.

    Args:
        selected_work_types: Tuple of work type names to filter by (must be tuple for caching)

    Returns:
        MuseumWorkTypeSummary with museums as keys and their artwork counts
    """
    start_time = time.time()
    logger.info(
        f"[CACHE] aggregate_museum_count called with {len(selected_work_types)} work types"
    )

    selected_work_types_list = list(selected_work_types)

    # Filter artworks that have at least one of the selected work types
    # Use PostgreSQL's ?| operator for efficient array overlap check (single index lookup)
    query_build_start = time.time()
    logger.info(
        f"[TIMING] aggregate_museum_count - Query build: {(time.time() - query_build_start) * 1000:.2f}ms"
    )

    query_exec_start = time.time()
    museum_counts = (
        ArtworkStats.objects.extra(
            where=["searchable_work_types ?| %s"], params=[selected_work_types_list]
        )
        .values("museum_slug")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    museums = {item["museum_slug"]: item["count"] for item in museum_counts}
    total = sum(museums.values())
    logger.info(
        f"[TIMING] aggregate_museum_count - Query execution: {(time.time() - query_exec_start) * 1000:.2f}ms"
    )

    elapsed = (time.time() - start_time) * 1000
    logger.info(
        f"[TIMING] aggregate_museum_count_for_selected_work_types - TOTAL: {elapsed:.2f}ms"
    )

    return MuseumWorkTypeSummary(work_types=museums, total=total)


@register_cache
@lru_cache(maxsize=1024)
def get_total_works_for_filters(
    selected_museums: tuple[str], selected_work_types: tuple[str]
) -> int:
    """
    Returns the total count of unique artworks that match BOTH museum AND work type filters.
    Used on every search, so must be fast.

    Args:
        selected_museums: Tuple of museum slugs to filter by (must be tuple for caching)
        selected_work_types: Tuple of work type names to filter by (must be tuple for caching)

    Returns:
        Integer count of unique artworks matching both filters
    """
    start_time = time.time()
    logger.info(
        f"[CACHE] get_total_works called: {len(selected_museums)} museums, {len(selected_work_types)} work types"
    )

    # Build query for artworks matching museum filter AND at least one work type
    # Use PostgreSQL's ?| operator for efficient array overlap check (single index lookup)
    query_build_start = time.time()
    logger.info(
        f"[TIMING] get_total_works - Query build: {(time.time() - query_build_start) * 1000:.2f}ms"
    )

    count_start = time.time()
    result = (
        ArtworkStats.objects.filter(museum_slug__in=selected_museums)
        .extra(
            where=["searchable_work_types ?| %s"], params=[list(selected_work_types)]
        )
        .count()
    )
    logger.info(
        f"[TIMING] get_total_works - COUNT query: {(time.time() - count_start) * 1000:.2f}ms"
    )

    elapsed = (time.time() - start_time) * 1000
    logger.info(f"[TIMING] get_total_works_for_filters - TOTAL: {elapsed:.2f}ms")

    return result


@register_cache
@lru_cache(maxsize=1)
def get_work_type_names() -> list[str]:
    """
    Returns all work types across all museums, sorted alphabetically.

    Cached with LRU cache (maxsize=1) since work types are stable.
    Cache is per-process and cleared on deployment/restart.

    Returns:
        Sorted list of all unique work type names
    """
    start_time = time.time()

    # Use PostgreSQL's jsonb_array_elements_text to get distinct work types at database level
    # This is 100x faster than fetching all rows and looping in Python
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT work_type
            FROM
                artsearch_artworkstats,
                jsonb_array_elements_text(searchable_work_types) as work_type
            ORDER BY work_type
            """
        )

        result = [row[0] for row in cursor.fetchall()]

    elapsed = (time.time() - start_time) * 1000
    logger.info(
        f"[TIMING] get_work_type_names - TOTAL: {elapsed:.2f}ms (cached for subsequent calls)"
    )

    return result
