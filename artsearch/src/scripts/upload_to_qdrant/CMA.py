"""
This script fetches data from the CMA API, processes it, and uploads it
to a Qdrant collection.
"""

from artsearch.src.scripts.upload_to_qdrant.upload_utils import upload_to_qdrant


# Constants
MUSEUM_NAME = "cma"
WORK_TYPES = [
    "Print",
    "Painting",
    "Drawing",
]
QUERY_TEMPLATE = {
    "q": "",
    "has_image": 1,
    "cc0": 1,
}


def main() -> None:
    upload_to_qdrant(
        limit=100,
        work_types=WORK_TYPES,
        query_template=QUERY_TEMPLATE,
        museum_name=MUSEUM_NAME,
    )


if __name__ == "__main__":
    main()
