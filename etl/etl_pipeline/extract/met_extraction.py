import logging
import requests
import time
from datetime import timedelta
from django.utils import timezone
from etl.etl_pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.models import MetaDataRaw
from artsearch.src.services.museum_clients.met_api_client import METAPIClient


MUSEUM_SLUG = "met"
CHUNK_SIZE = 100

MET_DEPARTMENTS = {
    11: "European Paintings",
    15: "The Robert Lehman Collection",
    9: "Drawings and Prints",
}

SEARCH_QUERIES = ["paintings"]

BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
OBJECTS_URL = f"{BASE_URL}/objects"
SEARCH_URL = f"{BASE_URL}/search"

ALREADY_UPSERTED = set()
SKIP_RECENT_DAYS = 30


def filter_recent_objects(object_ids: list[int]) -> list[int]:
    """
    Filter out objects that were fetched within the last SKIP_RECENT_DAYS days.
    Returns only object IDs that need to be re-fetched.
    """
    cutoff_date = timezone.now() - timedelta(days=SKIP_RECENT_DAYS)

    # Get all recent objects from database
    recent_objects = MetaDataRaw.objects.filter(
        museum_slug=MUSEUM_SLUG,
        museum_object_id__in=[str(obj_id) for obj_id in object_ids],
        fetched_at__gte=cutoff_date,
    ).values_list("museum_object_id", flat=True)

    recent_object_ids = {int(obj_id) for obj_id in recent_objects}

    # Filter out recent objects
    objects_to_fetch = [
        obj_id for obj_id in object_ids if obj_id not in recent_object_ids
    ]

    print(f"Total objects: {len(object_ids)}")
    print(f"Recently fetched (skipping): {len(recent_object_ids)}")
    print(f"Objects to fetch: {len(objects_to_fetch)}")
    return objects_to_fetch


def handle_met_upload(
    met_api_client: METAPIClient,
    object_ids: list[int],
) -> None:
    start_time = time.time()

    # Filter out recently fetched objects
    objects_to_fetch = filter_recent_objects(object_ids)

    if not objects_to_fetch:
        print("No objects need fetching - all are recently updated.")
        return

    total_num_changed = 0
    num_changed = 0
    for idx, object_id in enumerate(objects_to_fetch):
        print(f"Processing {idx + 1} of {len(objects_to_fetch)} objects...")

        time.sleep(5)  # to avoid rate limiting

        try:
            item = met_api_client.get_item(object_id)
        except requests.RequestException:
            continue

        changed = store_raw_data(
            museum_slug=MUSEUM_SLUG,
            object_id=str(object_id),
            raw_json=item,
        )
        print(f"Object {object_id} changed: {changed}")
        if changed:
            num_changed += 1
            total_num_changed += 1

        if idx % CHUNK_SIZE == 0:
            logging.info(f"Number of items changed in current batch: {num_changed}")
            num_changed = 0

    print(f"Total number of items changed: {total_num_changed}")
    print(f"Total time taken: {time.time() - start_time:.2f} seconds")


def store_raw_data_met():
    all_object_ids = set()
    met_api_client = METAPIClient()

    # Department-wise object IDs
    for department_id in MET_DEPARTMENTS.keys():
        object_ids = met_api_client.get_dept_object_ids(department_id)
        all_object_ids.update(set(object_ids))

    # Search queries for object IDs
    for query in SEARCH_QUERIES:
        query_params = {
            # "isHighlight": "true",
            "hasImages": "true",
            "q": query,  # has to come last, otherwise it will not work
        }
        object_ids = met_api_client.get_object_ids_by_search(
            query_params=query_params,
        )
        all_object_ids.update(set(object_ids))

    all_object_ids = sorted(list(all_object_ids))
    handle_met_upload(met_api_client, all_object_ids)
