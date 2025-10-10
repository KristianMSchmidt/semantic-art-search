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


@dataclass
class MuseumWorkTypeSummary:
    work_types: dict[str, int]
    total: int


@lru_cache(maxsize=1)
def aggregate_work_type_counts(
    collection_name: str = config.qdrant_collection_name_app,
    work_type_key: str = "searchable_work_types",
) -> tuple[MuseumWorkTypeCount, MuseumTotalCount]:
    logging.info("Counting work types")
    start_time = time.time()
    qdrant_service = get_qdrant_service()

    # Step 1: Scroll through all points to get museum and work_types
    work_counts: MuseumWorkTypeCount = defaultdict(lambda: defaultdict(int))
    total_counts: MuseumTotalCount = defaultdict(int)

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
    return work_counts, total_counts


def aggregate_work_type_count_for_selected_museums(
    selected_museums: Sequence[str],
    work_type_key: str = "searchable_work_types",
) -> MuseumWorkTypeSummary:
    """
    Aggregates work type counts and total work count for the given museums.
    """
    # Fetch per‐museum breakdowns
    work_counts, total_counts = aggregate_work_type_counts(work_type_key=work_type_key)

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


@lru_cache(maxsize=1)
def get_work_type_names() -> list[str]:
    """
    Returns all work types across all museums.
    """
    work_counts, _ = aggregate_work_type_counts()
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
