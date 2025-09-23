import logging
import requests
import time
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.models import MetaDataRaw


MUSEUM_SLUG = "met"
CHUNK_SIZE = 10  # how many items to process before logging progress

MET_DEPARTMENTS = {
    11: "European Paintings",
    15: "The Robert Lehman Collection",
    9: "Drawings and Prints",
}

SEARCH_QUERIES = ["paintings"]

BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
OBJECTS_URL = f"{BASE_URL}/objects"
SEARCH_URL = f"{BASE_URL}/search"
SLEEP_BETWEEN_REQUESTS = 1  # seconds


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
    max_retries = 3
    for attempt in range(max_retries):
        try:
            item = http_session.get(object_url, timeout=10)
            item.raise_for_status()
            return item.json()
        except requests.RequestException as e:
            print(
                f"Attempt {attempt + 1} failed for object {object_id}: {e}. Retrying..."
            )
            time.sleep(3**attempt)  # Exponential backoff: 1s, 3s, 9s
    raise RuntimeError(
        f"Failed to fetch object {object_id} after {max_retries} attempts"
    )


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


def filter_objects(object_ids: list[int]) -> list[int]:
    """
    Filter out objects that we don't need to fetch.
    Returns only object IDs that need to be re-fetched.
    """

    objects_to_skip = MetaDataRaw.objects.filter(
        museum_slug=MUSEUM_SLUG,
        museum_db_id__in=[str(obj_id) for obj_id in object_ids],
    ).values_list("museum_db_id", flat=True)

    object_ids_to_skip = {int(obj_id) for obj_id in objects_to_skip}

    objects_to_fetch = [
        obj_id for obj_id in object_ids if obj_id not in object_ids_to_skip
    ]

    print(f"Total objects: {len(object_ids)}")
    print(f"Already fetched (skipping): {len(object_ids_to_skip)}")
    print(f"Objects to fetch: {len(objects_to_fetch)}")
    return objects_to_fetch


def handle_met_upload(
    http_session: requests.Session,
    object_ids: list[int],
    force_refetch: bool = False,
) -> None:
    start_time = time.time()

    if force_refetch:
        objects_to_fetch = object_ids
    else:
        objects_to_fetch = filter_objects(object_ids)

    if not objects_to_fetch:
        print("No objects need fetching - all are already fetched")
        return

    num_created = 0
    num_updated = 0
    total_num_created = 0
    total_num_updated = 0

    for idx, object_id in enumerate(objects_to_fetch):
        print(f"Processing {idx + 1} of {len(objects_to_fetch)} objects...")

        time.sleep(SLEEP_BETWEEN_REQUESTS)  # to avoid rate limiting

        try:
            item = get_item(object_id, http_session)
            object_number = item["accessionNumber"]
        except requests.RequestException:
            continue

        created = store_raw_data(
            museum_slug=MUSEUM_SLUG,
            object_number=object_number,
            raw_json=item,
            museum_db_id=str(object_id),
        )

        if created:
            total_num_created += 1
            num_created += 1
        else:
            total_num_updated += 1
            num_updated += 1

        if idx % CHUNK_SIZE == 0 and idx > 0:
            logging.info(f"Number of items created in current batch: {num_created}")
            logging.info(f"Number of items updated in current batch: {num_updated}")
            num_created = 0
            num_updated = 0

    print(f"Total number of items created: {total_num_created}")
    print(f"Total number of items updated: {total_num_updated}")
    print(f"Total time taken: {time.time() - start_time:.2f} seconds")


def store_raw_data_met(force_refetch: bool = False) -> None:
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
    handle_met_upload(http_session, all_object_ids, force_refetch=force_refetch)
