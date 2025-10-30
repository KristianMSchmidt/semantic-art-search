import time
from typing import Sequence
from functools import lru_cache
from collections import defaultdict
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.config import config
from dataclasses import dataclass


import logging

logging.basicConfig(level=logging.INFO)


MuseumWorkTypeCount = dict[str, dict[str, int]]
MuseumTotalCount = dict[str, int]
MuseumArtworkWorkTypes = dict[
    str, dict[int | str, set[str]]
]  # museum -> {artwork_id: {work_types}}


@dataclass
class MuseumWorkTypeSummary:
    work_types: dict[str, int]
    total: int


@lru_cache(maxsize=1)
def aggregate_work_type_counts(
    collection_name: str = config.qdrant_collection_name_app,
    work_type_key: str = "searchable_work_types",
) -> tuple[MuseumWorkTypeCount, MuseumTotalCount, MuseumArtworkWorkTypes]:
    logging.info("Counting work types")
    start_time = time.time()
    qdrant_service = get_qdrant_service()

    # Step 1: Scroll through all points to get museum and work_types
    work_counts: MuseumWorkTypeCount = defaultdict(lambda: defaultdict(int))
    total_counts: MuseumTotalCount = defaultdict(int)
    artwork_work_types: MuseumArtworkWorkTypes = defaultdict(dict)

    next_page_token = None

    while True:
        points, next_page_token = qdrant_service.fetch_points(
            collection_name,
            next_page_token,
            limit=2000,
            with_payload=["museum", work_type_key],
        )
        for point in points:
            payload = point.payload
            if payload is None:
                logging.warning(f"Skipping point with missing payload: {point}")
                continue
            museum = payload.get("museum")
            if museum is None:
                logging.warning(f"Skipping point with missing museum: {point}")
                continue
            work_types = payload.get(work_type_key, [])
            if not isinstance(work_types, list):
                logging.warning(f"Skipping point with invalid work_types: {point}")
                continue

            # Store the work types for this artwork
            artwork_work_types[museum][point.id] = set(work_types)

            for work_type in work_types:
                work_counts[museum][work_type] += 1
            total_counts[museum] += 1

        if next_page_token is None:
            break

    # For each museum order the work types by count
    for museum, museum_count in work_counts.items():
        work_counts[museum] = dict(
            sorted(museum_count.items(), key=lambda x: x[1], reverse=True)
        )
    logging.info(f"Counted work types in {time.time() - start_time:.2f} seconds")
    return work_counts, total_counts, artwork_work_types


def aggregate_work_type_count_for_selected_museums(
    selected_museums: Sequence[str],
    work_type_key: str = "searchable_work_types",
) -> MuseumWorkTypeSummary:
    """
    Aggregates work type counts and total work count for the given museums.
    """
    # Fetch per‐museum breakdowns
    work_counts, total_counts, _ = aggregate_work_type_counts(
        work_type_key=work_type_key
    )

    combined_work_types: dict[str, int] = defaultdict(int)
    combined_total = 0

    for museum in selected_museums:
        for work_type, count in work_counts[museum].items():
            combined_work_types[work_type] += count
        combined_total += total_counts[museum]

    # Ensure all work types are included, even if count is zero
    for work_type in get_work_type_names():
        if work_type not in combined_work_types:
            combined_work_types[work_type] = 0

    # Sort descending by count
    sorted_items = sorted(combined_work_types.items(), key=lambda x: x[1], reverse=True)
    sorted_work_types = dict(sorted_items)

    return MuseumWorkTypeSummary(work_types=sorted_work_types, total=combined_total)


def aggregate_museum_count_for_selected_work_types(
    selected_work_types: Sequence[str],
    work_type_key: str = "searchable_work_types",
) -> MuseumWorkTypeSummary:
    """
    Aggregates museum counts and total work count for the given work types.
    Returns counts per museum based on selected work types.
    Correctly counts unique artworks (avoids double-counting artworks with multiple work types).
    """
    # Fetch per‐museum breakdowns (uses cached data)
    _, total_counts, artwork_work_types = aggregate_work_type_counts(
        work_type_key=work_type_key
    )

    # Optimization: if all work types are selected, use total_counts directly
    all_work_types = get_work_type_names()
    if set(selected_work_types) == set(all_work_types):
        combined_total = sum(total_counts.values())
        return MuseumWorkTypeSummary(
            work_types=dict(total_counts), total=combined_total
        )

    museum_counts: dict[str, int] = defaultdict(int)
    combined_total = 0

    selected_work_types_set = set(selected_work_types)

    for museum, artworks in artwork_work_types.items():
        # Count unique artworks that have at least one of the selected work types
        for artwork_work_type_set in artworks.values():
            if artwork_work_type_set.intersection(selected_work_types_set):
                museum_counts[museum] += 1

        combined_total += museum_counts[museum]

    # Sort descending by count
    sorted_items = sorted(museum_counts.items(), key=lambda x: x[1], reverse=True)
    sorted_museums = dict(sorted_items)

    return MuseumWorkTypeSummary(work_types=sorted_museums, total=combined_total)


def get_total_works_for_filters(
    selected_museums: Sequence[str],
    selected_work_types: Sequence[str],
    work_type_key: str = "searchable_work_types",
) -> int:
    """
    Returns the total count of unique artworks that match BOTH museum AND work type filters.
    Uses cached data for fast computation.
    """
    _, _, artwork_work_types = aggregate_work_type_counts(work_type_key=work_type_key)

    total_count = 0
    selected_work_types_set = set(selected_work_types)

    for museum in selected_museums:
        artworks = artwork_work_types.get(museum, {})
        for artwork_work_type_set in artworks.values():
            if artwork_work_type_set.intersection(selected_work_types_set):
                total_count += 1
    return total_count


@lru_cache(maxsize=1)
def get_work_type_names() -> list[str]:
    """
    Returns all work types across all museums.
    """
    work_counts, _, _ = aggregate_work_type_counts()
    all_work_types = set()
    for museum_work_types in work_counts.values():
        all_work_types.update(museum_work_types.keys())
    return sorted(all_work_types)


if __name__ == "__main__":
    # Set work_type_key = "work_types" to get all the work types in original language
    # Set work_type_key = "searchable_work_types" to get the shortened work types in English
    work_type_key = "searchable_work_types"
    musems = ["met"]
    for museum in musems:
        work_type_summary = aggregate_work_type_count_for_selected_museums(
            selected_museums=[museum], work_type_key=work_type_key
        )
        print(f"Combined work types for {museum}:")
        for work_type, count in work_type_summary.work_types.items():
            print(f"  {work_type}: {count}")
        print(f"  Total: {work_type_summary.total}")
        print()
