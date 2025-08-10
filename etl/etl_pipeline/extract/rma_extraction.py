import logging
import requests
import time
from typing import Any
import xmltodict
from etl.etl_pipeline.extract.helpers.upsert_raw_data import store_raw_data
from artsearch.src.services.museum_clients.rma_api_client import (
    extract_query_param,
)

MUSEUM_SLUG = "rma"
WORK_TYPES = [
    "painting",
    "drawing",
]
BASE_QUERY = {}
BASE_SEARCH_URL = "https://data.rijksmuseum.nl/search/collection"
GET_RECORD_URL = "https://data.rijksmuseum.nl/oai?verb=GetRecord&metadataPrefix=edm&identifier=https://id.rijksmuseum.nl/"
STATS = {}


def fetch_record(item_id: str, http_session: requests.Session) -> dict[str, Any]:
    item_url = GET_RECORD_URL + item_id
    response = http_session.get(item_url)
    response.raise_for_status()
    data = xmltodict.parse(response.content)
    record = data["OAI-PMH"]["GetRecord"]["record"]
    return record


def fetch_raw_data_from_rma_api(
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
    total_count = data["partOf"]["totalItems"]
    items = data.get("orderedItems", [])
    next = data.get("next", None)
    next_page_token = extract_query_param(next["id"], "pageToken") if next else None

    return {
        "total_count": total_count,
        "items": items,
        "next_page_token": next_page_token,
    }


def store_raw_data_rma():
    start_time = time.time()

    http_session = requests.Session()

    for work_type in WORK_TYPES:
        logging.info(f"Processing work type: {work_type}")

        total_num_changed = 0
        items_to_far = 0
        page_token = ""

        while True:
            num_changed = 0
            base_query = BASE_QUERY.copy()
            query = base_query | {
                "type": work_type,
                "pageToken": page_token,
            }

            try:
                data = fetch_raw_data_from_rma_api(query, http_session)
            except requests.RequestException as e:
                logging.error(
                    f"Failed to fetch data for work type {work_type} at page token {page_token}: {e}"
                )
                break

            items = data.get("items", [])
            total = data.get("total_count", 0)
            items_to_far += len(items)
            next_page_token = data.get("next_page_token", None)

            logging.info(
                f"Upserting {len(items)} items. Items so far: {items_to_far}/{total} for work type: {work_type}."
            )

            for item in items:
                item_id = item["id"].split("/")[-1]
                record = fetch_record(item_id, http_session)
                changed = store_raw_data(
                    museum_slug=MUSEUM_SLUG,
                    object_id=item_id,
                    raw_json=record,
                )
                if changed:
                    num_changed += 1
                    total_num_changed += 1

            logging.info(f"Number of items changed in current batch: {num_changed}")

            if next_page_token is None or not next_page_token.strip():
                logging.info(f"All items processed for work type: {work_type}.")
                logging.info(
                    f"Total items changed for {work_type}: {total_num_changed}"
                )
                break
            page_token = next_page_token

    print(f"Total time taken: {time.time() - start_time:.2f} seconds")
