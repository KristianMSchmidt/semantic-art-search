import logging
import requests
import time
from datetime import timedelta
from django.utils import timezone
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.models import MetaDataRaw


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


def get_dept_object_ids(
    department_id: int, http_session: requests.Session
) -> list[int]:
    """Fetch object IDs for a given department ID from the MET API."""
    url = f"{OBJECTS_URL}?departmentIds={department_id}"
    try:
        resp = http_session.get(url)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching department {department_id} object IDs: {e}")
        raise
    else:
        return resp.json().get("objectIDs", [])


def get_item(object_id: int, http_session: requests.Session) -> dict:
    """Fetch a single artwork item from the MET API."""
    object_url = f"{OBJECTS_URL}/{object_id}"
    try:
        item = http_session.get(object_url, timeout=10)
        item.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching object {object_id}: {e}")
        raise
    else:
        return item.json()


def get_object_ids_by_search(
    query_params: dict, http_session: requests.Session
) -> list[int]:
    """Search for items in the MET collection using query parameters"""
    try:
        resp = http_session.get(SEARCH_URL, params=query_params)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error searching items: {e}")
        raise
    else:
        return resp.json().get("objectIDs", [])


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
        last_updated__gte=cutoff_date,
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
    http_session: requests.Session,
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
            item = get_item(object_id, http_session)
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
    http_session = requests.Session()

    # Department-wise object IDs
    for department_id in MET_DEPARTMENTS.keys():
        object_ids = get_dept_object_ids(department_id, http_session)
        all_object_ids.update(set(object_ids))

    # Search queries for object IDs
    for query in SEARCH_QUERIES:
        query_params = {
            # "isHighlight": "true",
            "hasImages": "true",
            "q": query,  # has to come last, otherwise it will not work
        }
        object_ids = get_object_ids_by_search(
            query_params=query_params,
            http_session=http_session,
        )
        all_object_ids.update(set(object_ids))

    all_object_ids = sorted(list(all_object_ids))
    handle_met_upload(http_session, all_object_ids)
