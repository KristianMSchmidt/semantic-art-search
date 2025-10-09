import requests
import time
import logging

from artsearch.src.services.bucket_service import BucketService
from artsearch.src.config import config
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.scripts.upload_to_qdrant.upload_utils import prepare_point_struct
from artsearch.src.services.clip_embedder import get_clip_embedder, CLIPEmbedder
from artsearch.src.services.museum_clients.met_api_client import METAPIClient

qdrant_service = get_qdrant_service()
clip_embedder = get_clip_embedder()
met_api_client = METAPIClient()
bucket_service = BucketService(use_etl_bucket=True)

CHUNK_SIZE = 100

MET_DEPARTMENTS = {
    9: "Drawings and Prints",  # Many! Probably too many. Wait with this one.
    # 11: "European Paintings",  # DONE!
    # 15: "The Robert Lehman Collection",  # DONE!
}


def handle_met_upload(
    object_ids: list[int],
    met_api_client: METAPIClient = met_api_client,
    clip_embedder: CLIPEmbedder = clip_embedder,
) -> None:
    """Handles the upload of MET objects to Qdrant and the Linode bucket."""
    success_count = 0
    for i in range(0, len(object_ids), CHUNK_SIZE):
        chunk = object_ids[i : i + CHUNK_SIZE]
        print(
            f"Processing chunk {i // CHUNK_SIZE + 1} of {len(object_ids) // CHUNK_SIZE + 1}"
        )
        already_in_qdrant = qdrant_service.get_existing_values(
            values=chunk,
            museum="met",
            id_key="museum_db_id",
        )
        filtered_chunk = [id for id in chunk if id not in already_in_qdrant]
        print(len(filtered_chunk), "objects to process in this chunk.")

        if not filtered_chunk:
            print("No new objects to process in this chunk.")
            continue

        time.sleep(5)
        for object_id in filtered_chunk:
            time.sleep(3)

            # Step 1: Fetch and process artwork item from MET
            try:
                item = met_api_client.get_item(object_id)
            except requests.RequestException:
                continue

            # Step 2: Make artwork payload from the item
            try:
                artwork_payload = met_api_client.process_item(item)  # type: ignore
                assert artwork_payload is not None, "Processed item should not be None"
            except Exception as e:
                logging.error(f"Error preparing payload for item {object_id}: {e}")
                continue

            # Step 3: Prepare point struct for Qdrant
            point = prepare_point_struct(
                artwork_payload,
                clip_embedder,
                "met",
            )
            if point is None:
                continue

            # Step 4: Upload image to bucket
            try:
                bucket_service.upload_thumbnail(
                    museum="met",
                    object_number=artwork_payload.object_number,
                    museum_image_url=artwork_payload.thumbnail_url,
                )
            except Exception as e:
                logging.error(
                    f"Failed to upload thumbnail for {artwork_payload.object_number}: {e}"
                )
                continue

            # Step 5: Upload to qdrant (after thumbnail upload)
            try:
                qdrant_service.qdrant_client.upsert(
                    collection_name=config.qdrant_collection_name,
                    points=[point],
                )

            except Exception as e:
                logging.error(f"Failed to upsert point {object_id} to Qdrant: {e}")
                continue

            success_count += 1
    print(f"Successfully uploaded {success_count} objects to Qdrant.")


def upload_MET_departments():
    for department_id in MET_DEPARTMENTS:
        department_object_ids = met_api_client.get_dept_object_ids(department_id)
        department_name = MET_DEPARTMENTS[department_id]
        print(
            f"Uploading {len(department_object_ids)} objects from {department_name} (ID: {department_id})..."
        )
        handle_met_upload(department_object_ids)


def upload_highlighted_paintings():
    query_params = {
        # "isHighlight": "true",
        "hasImages": "true",
        "q": "painting",  # painting",  # has to come last, otherwise it will not work
    }
    object_ids = met_api_client.get_object_ids_by_search(
        query_params=query_params,
    )
    print(f"Found {len(object_ids)} highlighted paintings.")

    handle_met_upload(object_ids)


if __name__ == "__main__":
    # upload_MET_departments()
    upload_highlighted_paintings()
