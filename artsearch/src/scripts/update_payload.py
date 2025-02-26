"""
Script to update the payload of existing qdrant collection.
"""

import logging
from typing import cast
from qdrant_client import models
from artsearch.src.services.qdrant_service import get_qdrant_service

COLLECTION_NAME = "smk_artworks_dev_l_14"

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def update_payload(old_payload: dict) -> dict:
    new_payload = old_payload.copy()
    new_payload["object_names_flattened"] = [
        object_name.get("name").lower() for object_name in old_payload["object_names"]
    ]
    return new_payload


def process_points(points: list[models.Record]) -> list[models.PointStruct]:
    processed_points = []
    for point in points:
        if not point.vector:
            raise ValueError(
                f"Point {point.id} has an invalid or missing vector: {point.vector}"
            )
        if not point.payload or "object_names" not in point.payload:
            raise ValueError(
                f"Point {point.id} has an invalid or missing payload: {point.payload}"
            )
        new_payload = update_payload(point.payload)
        new_vector = cast(list[float], point.vector)
        processed_points.append(
            models.PointStruct(id=str(point.id), payload=new_payload, vector=new_vector)
        )
    return processed_points


def main() -> None:
    """Main entry point of the script."""
    qdrant_service = get_qdrant_service()

    next_page_token = None

    num_points = 0

    while True:
        points, next_page_token = qdrant_service.fetch_points(
            COLLECTION_NAME, next_page_token, limit=1000, with_vectors=True
        )
        processed_points = process_points(points)
        qdrant_service.upload_points(processed_points, COLLECTION_NAME)
        num_points += len(points)
        if next_page_token is None:  # No more points left
            break
    logging.info(
        f"Successfully updated {num_points} points in collection {COLLECTION_NAME}."
    )


if __name__ == "__main__":
    main()
