"""
This script fetches data from the SMK API, processes it, and uploads it
to a Qdrant collection.
"""

import logging
import uuid
from typing import Any, List
from qdrant_client.http.models import PointStruct
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.smk_api_client import SMKAPIClient
from artsearch.src.config import clip_selection


# Constants
CLIP_MODEL_NAME: clip_selection = "ViT-L/14"
UPLOAD_COLLECTION_NAME = "smk_artworks_dev_l_14"
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
OBJECT_NAMES = [
    'tegning',
    'akvatinte',
    'Buste' 'Altertavle (maleri)',
    'akvarel',
    'Altertavle (maleri)',
    'Buste' 'maleri',
    'pastel',
]

# Initialize SMK API Client
smk_api_client = SMKAPIClient()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO
)


def get_user_confirmation() -> None:
    """Prompt the user for confirmation before proceeding."""
    logging.info(
        f"This script will upload embedded data to the Qdrant collection: {UPLOAD_COLLECTION_NAME}, "
        f"using the CLIP model: {CLIP_MODEL_NAME}."
    )
    response = input("Do you want to proceed? (y/n): ").strip().lower()
    if response != "y":
        logging.info("Exiting the program.")
        exit()
    logging.info("Proceeding with the program...")


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


def process_items(
    data: dict[str, Any], embedder, already_uploaded_object_numbers: set[str]
) -> List[PointStruct]:
    """Process items from SMK API data and return a list of Qdrant PointStruct."""
    points = []
    for item in data.get("items", []):
        object_number = item['object_number']
        if object_number in already_uploaded_object_numbers:
            continue
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
                logging.warning(
                    f"Skipping item {item['object_number']} due to embedding failure."
                )
        except KeyError as e:
            logging.error(f"Missing key in item: {e}")
    return points


def main() -> None:
    """Main entry point of the script."""
    qdrant_service = get_qdrant_service()
    clip_embedder = get_clip_embedder(model_name=CLIP_MODEL_NAME)

    # Create collection if it doesn't exist
    qdrant_service.create_qdrant_collection(
        collection_name=UPLOAD_COLLECTION_NAME,
        dimensions=clip_embedder.embedding_dim,
    )

    already_uploaded_object_numbers = qdrant_service.get_all_object_numbers(
        collection_name=UPLOAD_COLLECTION_NAME
    )

    total_points = 0

    for object_name in OBJECT_NAMES:
        logging.info(f"Processing object name: {object_name}")
        offset = 0

        while True:
            query = {
                "keys": "*",
                "fields": ",".join(FIELDS),
                "filters": f"[has_image:true],[object_names:{object_name}],[public_domain:true]",
                "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
                "offset": offset,
                "rows": 250,  # Max is 2000
            }

            data = smk_api_client.fetch_data(query)

            if not data or not data.get("items"):
                logging.info(
                    f"No more items found for object name: {object_name} at offset {offset}."
                )
                break

            logging.info(
                f"Processing {len(data.get('items', []))} items at offset {offset} for object name: {object_name}."
            )
            points = process_items(data, clip_embedder, already_uploaded_object_numbers)

            if points:
                qdrant_service.qdrant_client.upsert(
                    collection_name=UPLOAD_COLLECTION_NAME, points=points
                )
                total_points += len(points)
                logging.info(
                    f"Uploaded {len(points)} points for object name: {object_name} at offset {offset}."
                )

            if offset + query["rows"] >= data["found"]:
                logging.info(f"All items processed for object name: {object_name}.")
                break

            offset += query["rows"]

    logging.info(f"Total points uploaded: {total_points}")


if __name__ == "__main__":
    get_user_confirmation()
    main()
