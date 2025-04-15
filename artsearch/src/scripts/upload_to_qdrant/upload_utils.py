"""
This script fetches data from the SMK API, processes it, and uploads it
to a Qdrant collection.
"""

import logging
import uuid
from qdrant_client.http.models import PointStruct
from artsearch.src.services.qdrant_service import QdrantService, get_qdrant_service

from artsearch.src.services.clip_embedder import (
    CLIPEmbedder,
    get_clip_embedder,
    clip_selection,
)
from artsearch.src.services.museum_clients import (
    SMKAPIClient,
    CMAAPIClient,
    ArtworkPayload,
    MuseumName,
)

# Constants
LIMIT = 100  # Number of items to fetch per request
CLIP_MODEL_NAME: clip_selection = "ViT-L/14"
UPLOAD_COLLECTION_NAME = "artworks_dev_2"


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def get_user_confirmation(
    clip_model_name: clip_selection,
    upload_collection_name: str,
    museum_name: MuseumName,
) -> None:
    """Prompt the user for confirmation before proceeding."""
    logging.info(
        f"You are about to upload embedded data from {museum_name} to Qdrant collection: {upload_collection_name}, "
        f"using the CLIP model: {clip_model_name}."
    )
    response = input("Do you want to proceed? (y/n): ").strip().lower()
    if response != "y":
        logging.info("Exiting the program.")
        exit()
    logging.info("Proceeding with the program...")


def generate_uuid5(museum_name: MuseumName, object_number: str) -> str:
    """Generate a UUID5 from the museum name and object number."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{museum_name}-{object_number}"))


def process_payloads(
    payloads: list[ArtworkPayload],
    embedder: CLIPEmbedder,
    qdrant_service: QdrantService,
    museum_name: MuseumName,
    upload_collection_name: str,
    work_type_translations: dict[str, str] | None = None,
) -> list[PointStruct]:
    """Process items and return a list of Qdrant PointStruct."""
    points = []

    # Batch check for existing object numbers
    object_numbers = [payload.object_number for payload in payloads]
    existing_object_numbers = qdrant_service.get_existing_object_numbers(
        upload_collection_name, object_numbers, museum_name
    )
    for payload in payloads:
        object_number = payload.object_number
        if object_number in existing_object_numbers:
            continue  # Skip if already uploaded

        if work_type_translations:
            payload.work_types = [
                work_type_translations[work_type] for work_type in payload.work_types
            ]
        try:
            vector = embedder.generate_thumbnail_embedding(
                payload.thumbnail_url, museum_name, object_number, cache=True
            )
            if vector is not None:
                point_id = generate_uuid5(museum_name, object_number)
                points.append(
                    PointStruct(
                        id=point_id, payload=payload.model_dump(), vector=vector
                    )
                )
            else:
                logging.warning(
                    f"Skipping payload {object_number} due to embedding failure."
                )
        except KeyError as e:
            logging.error(f"Missing key in payload: {e}")

    return points


def upload_to_qdrant(
    work_types: list[str],
    query_template: dict,
    museum_name: MuseumName,
    clip_model_name: clip_selection = CLIP_MODEL_NAME,
    upload_collection_name: str = UPLOAD_COLLECTION_NAME,
    work_type_translations: dict[str, str] | None = None,
) -> None:
    """Upload museum data to Qdrant"""
    get_user_confirmation(clip_model_name, upload_collection_name, museum_name)

    qdrant_service = get_qdrant_service()
    clip_embedder = get_clip_embedder(model_name=clip_model_name)

    # Create collection if it doesn't exist
    qdrant_service.create_qdrant_collection(
        collection_name=upload_collection_name,
        dimensions=clip_embedder.embedding_dim,
    )

    total_points = 0

    for work_type in work_types:
        logging.info(f"Processing work type: {work_type}")
        offset = 0

        while True:
            if museum_name == "smk":
                query_template["filters"] = (
                    f"[has_image:true],[object_names:{work_type}],[public_domain:true]",
                )
                query_template["offset"] = offset
                query_template["rows"] = LIMIT
                museum_api_client = SMKAPIClient()
            elif museum_name == "cma":
                query_template["type"] = work_type
                query_template["skip"] = offset
                query_template["limit"] = LIMIT
                museum_api_client = CMAAPIClient()

            response = museum_api_client.fetch_processed_data(query_template)
            items = response.items
            total = response.total

            if not items:
                logging.info(
                    f"No more items found for work type: {work_type} at offset {offset}."
                )
                break

            logging.info(
                f"Processing {len(items)} items at offset {offset}/{total} for work type: {work_type}."
            )
            points = process_payloads(
                items,
                clip_embedder,
                qdrant_service,
                museum_name,
                upload_collection_name,
                work_type_translations,
            )
            if points:
                qdrant_service.qdrant_client.upsert(
                    collection_name=upload_collection_name, points=points
                )
                total_points += len(points)
                logging.info(
                    f"Uploaded {len(points)} points for work type: {work_type} at offset {offset}."
                )

            if offset + LIMIT >= total:
                logging.info(f"All items processed for work type: {work_type}.")
                break

            offset += LIMIT

    logging.info(f"Total points uploaded: {total_points}")
