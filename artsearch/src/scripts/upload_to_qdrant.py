"""
This script fetches data from the SMK API, processes it, and uploads it
to a Qdrant collection.
"""

from typing import Any
import uuid
from qdrant_client.http.models import PointStruct
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.smk_api_client import SMKAPIClient
from artsearch.src.config import config

smk_api_client = SMKAPIClient()

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
OBJECT_NAME = "Buste"
# "paster"  # "akvatinte"  # "Altertavle (maleri)"  # "akvarel"  # "maleri"
QUERY_TEMPLATE = {
    "keys": "*",
    "fields": ",".join(FIELDS),
    "filters": f"[has_image:true],[object_names:{OBJECT_NAME}],[public_domain:true]",
    "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
    "offset": 0,
    "rows": 250,  # Max is 2000
}


def get_user_confirmation() -> None:
    """Prompt the user for confirmation before proceeding."""
    response = input("Do you want to proceed? (y/n): ").strip().lower()
    if response != "y":
        print("Exiting the program.")
        exit()
    print("Proceeding with the program...")


def prepare_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Prepare payload for Qdrant PointStruct."""
    return {
        "object_number": item["object_number"],
        "titles": item.get("titles", []),
        "object_names": item.get("object_names", []),
        "artist": item.get("artist", []),
        "production_date_start": item["production_date"][0]["start"].split("-")[0],
        "production_date_end": item["production_date"][0]["end"].split("-")[0],
        "thumbnail_url": item["image_thumbnail"],
    }


def process_items(data: dict[str, Any], embedder) -> list[PointStruct]:
    """Process items from SMK API data and return a list of Qdrant PointStruct."""
    points = []
    for item in data.get("items", []):
        try:
            payload = prepare_payload(item)
            vector = embedder.generate_thumbnail_embedding(
                item["image_thumbnail"], item["object_number"], cache=True
            )
            if vector is not None:
                point_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(item["object_number"]))
                points.append(
                    PointStruct(id=str(point_id), payload=payload, vector=vector)
                )
            else:
                print(
                    f"Skipping item {item['object_number']} due to embedding failure."
                )
        except KeyError as e:
            print(f"Missing key in item: {e}")
    return points


def main() -> None:
    """Main entry point of the script."""

    qdrant_service = get_qdrant_service()
    clip_embedder = get_clip_embedder()

    # Create collection if it doesn't exist
    qdrant_service.create_qdrant_collection(
        collection_name=config.qdrant_collection_name,
        dimensions=512,
    )

    offset = 0
    total_points = 0

    while True:
        QUERY_TEMPLATE["offset"] = offset
        data = smk_api_client.fetch_data(QUERY_TEMPLATE)

        if not data or not data.get("items"):
            break

        print(f"Processing items for offset {offset}...")
        points = process_items(data, clip_embedder)

        if points:
            qdrant_service.qdrant_client.upsert(
                collection_name=config.qdrant_collection_name, points=points
            )
            total_points += len(points)

        if offset + QUERY_TEMPLATE["rows"] >= data["found"]:
            break

        offset += QUERY_TEMPLATE["rows"]

    print(f"Total points uploaded: {total_points}")


if __name__ == "__main__":
    get_user_confirmation()
    main()
