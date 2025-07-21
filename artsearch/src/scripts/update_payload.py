"""
Script to update the payload of existing qdrant collection.
"""

import logging
from typing import cast
from qdrant_client import models
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.config import config


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def adhoc_update_payload(old_payload: dict) -> dict:
    new_payload = old_payload.copy()
    ##### Change the section below depending on the update needed #####
    # old_thumbnail_url = new_payload["thumbnail_url"]
    # new_thumbnail_url = adjust_thumbnail_size(old_thumbnail_url)
    # new_payload["thumbnail_url"] = new_thumbnail_url
    #################

    return new_payload


def process_points(points: list[models.Record]) -> list[models.PointStruct]:
    processed_points = []
    for idx, point in enumerate(points):
        if not point.vector:
            raise ValueError(
                f"Point {point.id} has an invalid or missing vector: {point.vector}"
            )
        if not point.payload:
            raise ValueError(f"Point {point.id} has a missing payload: {point.payload}")

        new_payload = adhoc_update_payload(point.payload)
        new_vector = cast(list[float], point.vector)
        processed_points.append(
            models.PointStruct(id=str(point.id), payload=new_payload, vector=new_vector)
        )
    return processed_points


def main(collection_name: str = config.qdrant_collection_name) -> None:
    """Main entry point of the script."""
    qdrant_service = get_qdrant_service()

    next_page_token = None

    num_points = 0

    while True:
        points, next_page_token = qdrant_service.fetch_points(
            collection_name, next_page_token, limit=1000, with_vectors=True
        )
        processed_points = process_points(points)
        # qdrant_service.upload_points(processed_points, collection_name)
        num_points += len(points)
        if next_page_token is None:  # No more points left
            break
    logging.info(
        f"Successfully updated {num_points} points in collection {collection_name}."
    )


if __name__ == "__main__":
    main()
