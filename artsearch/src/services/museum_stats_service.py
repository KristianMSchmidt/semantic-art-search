import time
from functools import lru_cache
from collections import defaultdict
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.museum_clients import MuseumName
from artsearch.src.config import config
from dataclasses import dataclass


import logging

logging.basicConfig(level=logging.INFO)


MuseumWorkTypeCount = dict[MuseumName, dict[str, int]]
MuseumTotalCount = dict[MuseumName, int]


@dataclass
class MuseumWorkTypeSummary:
    work_types: dict[str, int]
    total: int


@lru_cache(maxsize=1)
def aggregate_work_type_counts(
    collection_name: str = config.qdrant_collection_name,
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
            with_payload=["museum", "work_types"],
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
            work_types = payload.get("work_types", [])
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


def get_work_type_counts_for_museum(
    museum: MuseumName,
) -> MuseumWorkTypeSummary:
    work_counts, total_counts = aggregate_work_type_counts()

    if museum == "all":
        # Combine work types across all museums
        combined_work_types: dict[str, int] = defaultdict(int)
        for museum_work_types in work_counts.values():
            for work_type, count in museum_work_types.items():
                combined_work_types[work_type] += count

        # Correct total count: sum artworks per museum, not per type
        combined_total = sum(total_counts.values())

        # Sort combined work types
        sorted_work_types = dict(
            sorted(combined_work_types.items(), key=lambda x: x[1], reverse=True)
        )
        return MuseumWorkTypeSummary(work_types=sorted_work_types, total=combined_total)

    # Regular single-museum case
    work_types = work_counts[museum]
    total = total_counts[museum]
    return MuseumWorkTypeSummary(work_types=work_types, total=total)


if __name__ == "__main__":
    musems: list[MuseumName] = ["smk", "cma", "all"]
    for museum in musems:
        work_type_summary = get_work_type_counts_for_museum(museum)
        print(f"Combined work types for {museum}:")
        for work_type, count in work_type_summary.work_types.items():
            print(f"  {work_type}: {count}")
        print(f"  Total: {work_type_summary.total}")
        print()
