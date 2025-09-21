import logging
import requests
import time
from typing import Any
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data

MUSEUM_SLUG = "smk"
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
WORK_TYPES = [
    "pastel",
    "akvatinte",
    "akvarel",
    "Buste",
    "maleri",
    "tegning",
]
LIMIT = 100
BASE_QUERY = {
    "keys": "*",
    # "fields": ",".join(FIELDS),
    # "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
    "rows": LIMIT,
}
BASE_URL = "https://api.smk.dk/api/v1/art/"
BASE_SEARCH_URL = f"{BASE_URL}search/"


def fetch_raw_data_from_smk_api(
    query: dict, http_session: requests.Session, base_search_url: str = BASE_SEARCH_URL
) -> dict[str, Any]:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = http_session.get(base_search_url, params=query, timeout=5)
            response.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")

    data = response.json()
    return {"total_count": data.get("found", 0), "items": data.get("items", [])}


def store_raw_data_smk(force_refetch: bool = False):
    start_time = time.time()

    http_session = requests.Session()

    for work_type in WORK_TYPES:
        logging.info(f"Processing work type: {work_type}")

        offset = 0
        total_num_created = 0
        total_num_updated = 0

        while True:
            num_created = 0
            num_updated = 0
            base_query = BASE_QUERY.copy()
            query = base_query | {
                "filters": f"[has_image:true],[object_names:{work_type}],[public_domain:true]",
                "offset": offset,
            }
            try:
                data = fetch_raw_data_from_smk_api(query, http_session)
            except requests.RequestException as e:
                logging.error(
                    f"Failed to fetch data for work type {work_type} at offset {offset}: {e}"
                )
                break

            items = data.get("items", [])
            total = data.get("total_count", 0)

            logging.info(
                f"Upserting {len(items)} items at offset {offset}/{total} for work type: {work_type}."
            )

            for item in items:
                created = store_raw_data(
                    museum_slug=MUSEUM_SLUG,
                    object_number=item["object_number"],
                    raw_json=item,
                    museum_db_id=item.get("id"),
                )
                if created:
                    num_created += 1
                    total_num_created += 1
                else:
                    num_updated += 1
                    total_num_updated += 1

            logging.info(f"Number of items created in current batch: {num_created}")
            logging.info(f"Number of items updated in current batch: {num_updated}")

            if offset + LIMIT >= total:
                logging.info(f"All items processed for work type: {work_type}.")
                logging.info(
                    f"Total items created for {work_type}: {total_num_created}"
                )
                logging.info(
                    f"Total items updated for {work_type}: {total_num_updated}"
                )
                break

            offset += LIMIT

    print(f"Total time taken: {time.time() - start_time:.2f} seconds")
