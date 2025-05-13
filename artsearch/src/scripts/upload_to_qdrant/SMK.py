"""
This script fetches data from the SMK API, processes it, and uploads it
to a Qdrant collection.
"""

from artsearch.src.services.museum_clients.base_client import MuseumName
from artsearch.src.scripts.upload_to_qdrant.upload_utils import upload_to_qdrant

MUSEUM_NAME: MuseumName = "smk"

FIELDS = [
    "titles",
    "artist",
    "object_names",
    "production_date",
    "object_number",
    "image_thumbnail",
]
START_DATE = "1000-01-01T00:00:00.000Z"
END_DATE = "2026-12-31T23:59:59.999Z"
WORK_TYPES = [
    "tegning",
    "akvatinte",
    "akvarel",
    "Altertavle (maleri)",
    "Buste",
    "maleri",
    "pastel",
]

QUERY_TEMPLATE = {
    "keys": "*",
    "fields": ",".join(FIELDS),
    "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
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
