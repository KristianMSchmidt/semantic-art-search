"""
Utility functions for uploading data to Qdrant
"""

import time
import logging
import uuid
import copy
from typing import Any
from qdrant_client.http.models import PointStruct
from artsearch.src.services.qdrant_service import QdrantService, get_qdrant_service

from artsearch.src.services.clip_embedder import (
    CLIPEmbedder,
    get_clip_embedder,
    ClipSelection,
)
from artsearch.src.services.museum_clients.base_client import (
    ArtworkPayload,
)
from artsearch.src.services.museum_clients.factory import get_museum_client

# Constants
CLIP_MODEL_NAME: ClipSelection = "ViT-L/14"
UPLOAD_COLLECTION_NAME = "artworks_dev_2"


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def get_user_confirmation(
    clip_model_name: ClipSelection,
    upload_collection_name: str,
    museum_name: str,
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


def generate_uuid5(museum_name: str, object_number: str) -> str:
    """Generate a UUID5 from the museum name and object number."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{museum_name}-{object_number}"))


def process_payloads(
    payloads: list[ArtworkPayload],
    embedder: CLIPEmbedder,
    qdrant_service: QdrantService,
    museum_name: str,
    upload_collection_name: str,
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

        try:
            vector = embedder.generate_thumbnail_embedding(
                payload.thumbnail_url, object_number
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


def build_query(
    base_query: dict,
    museum_name: str,
    work_type: str,
    offset: int,
    limit: int,
    page_token: str | None,
) -> dict:
    """
    Returns a new query dict based on the museum's API requirements.
    """
    query = copy.deepcopy(base_query)

    builders = {
        "smk": lambda q: q
        | {
            "filters": f"[has_image:true],[object_names:{work_type}],[public_domain:true]",
            "offset": offset,
            "rows": limit,
        },
        "cma": lambda q: q
        | {
            "type": work_type,
            "skip": offset,
            "limit": limit,
        },
        "rma": lambda q: q
        | {
            "type": work_type,
            "pageToken": page_token,
        },
    }

    if museum_name not in builders:
        raise ValueError(f"No query builder found for museum: {museum_name}")

    return builders[museum_name](query)


def upload_to_qdrant(
    work_types: list[str],
    query_template: dict[str, Any],
    museum_name: str,
    limit: int,
    clip_model_name: ClipSelection = CLIP_MODEL_NAME,
    upload_collection_name: str = UPLOAD_COLLECTION_NAME,
) -> int:
    """
    Uploads artworks from a museum API to a Qdrant collection with CLIP embeddings.

    For each specified work type, the function:
    - Fetches data from the museum API in batches.
    - Generates CLIP embeddings.
    - Uploads the embeddings and metadata to Qdrant.

    Args:
        work_types (list[str]): List of work types to process.
        query_template (dict): Base query template for the museum API.
        museum_name (str): Identifier for the museum ("smk", "cma", "rma").
        limit (int): Number of items fetched per request (default 100).
        clip_model_name (ClipSelection): CLIP model used for embedding.
        upload_collection_name (str): Target Qdrant collection name.
        work_type_translations (dict[str, str] | None): Optional translations for work types.


    Returns:
        int: Total number of points uploaded.
    """
    start_time = time.time()

    get_user_confirmation(clip_model_name, upload_collection_name, museum_name)

    qdrant_service = get_qdrant_service()
    clip_embedder = get_clip_embedder(model_name=clip_model_name)
    museum_api_client = get_museum_client(museum_name)

    # Create collection if it doesn't exist
    qdrant_service.create_qdrant_collection(
        collection_name=upload_collection_name,
        dimensions=clip_embedder.embedding_dim,
    )

    total_points = 0

    for work_type in work_types:
        logging.info(f"Processing work type: {work_type}")
        offset = 0
        page_token = "0"  # Currently only used for RMA

        while True:
            query = build_query(
                query_template, museum_name, work_type, offset, limit, page_token
            )
            response = museum_api_client.fetch_processed_data(query)

            items = response.items
            total = response.total
            page_token = response.next_page_token

            logging.info(
                f"Processing {len(items)} items at offset {offset}/{total} for work type: {work_type}."
            )

            points = process_payloads(
                items,
                clip_embedder,
                qdrant_service,
                museum_name,
                upload_collection_name,
            )

            if points:
                qdrant_service.qdrant_client.upsert(
                    collection_name=upload_collection_name, points=points
                )
                total_points += len(points)
                logging.info(
                    f"Uploaded {len(points)} points for work type: {work_type} at offset {offset}."
                )

            if offset + limit >= total:
                logging.info(f"All items processed for work type: {work_type}.")
                break

            offset += limit

    duration = time.time() - start_time
    logging.info(
        f"Total points uploaded: {total_points} to collection '{upload_collection_name}' in {duration:.2f} seconds."
    )
    return total_points
