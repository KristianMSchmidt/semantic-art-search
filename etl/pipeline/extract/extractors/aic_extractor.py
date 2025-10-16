import logging
import requests
import time
from typing import Any
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


MUSEUM_SLUG = "aic"
LIMIT = 100  # Maximum allowed by AIC API
BASE_URL = "https://api.artic.edu/api/v1/artworks/search"
SLEEP_BETWEEN_REQUESTS = (
    1.5  # Seconds (rate limit: 60 req/min, this gives 40 req/min with safety margin)
)

# Fields to request from the API
FIELDS = [
    "id",
    "title",
    "artist_display",
    "date_start",
    "date_end",
    "date_display",
    "medium_display",
    "main_reference_number",
    "image_id",  # Used to construct IIIF image URLs
    "is_public_domain",  # Required for filtering
    "artwork_type_title",
    "artwork_type_id",
    "department_title",
    "artist_title",
    "category_titles",
    "term_titles",
    "style_title",
    "style_titles",
    "classification_title",
    "classification_titles",
    "material_titles",
    "technique_titles",
    "updated_at",
]


def fetch_raw_data_from_aic_api(
    query: dict, http_session: requests.Session, base_url: str = BASE_URL
) -> dict[str, Any]:
    """
    Fetch artwork data from the Art Institute of Chicago API.

    Returns:
        dict with keys:
            - total_count: Total number of artworks matching the query
            - items: List of artwork objects
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = http_session.get(base_url, params=query, timeout=30)
            response.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
            time.sleep(2**attempt)  # Exponential backoff

    data = response.json()
    pagination = data.get("pagination", {})

    return {
        "total_count": pagination.get("total", 0),
        "total_pages": pagination.get("total_pages", 0),
        "items": data.get("data", []),
    }


def store_raw_data_aic(force_refetch: bool = False):
    """
    Fetch and store raw artwork data from the Art Institute of Chicago API.

    Server-side filtering:
    - Public domain only (is_public_domain=true)

    Client-side validation:
    - Has image_id (required for image loading stage)
    - Has main_reference_number (our unique identifier)

    Work type filtering (paintings, drawings, etc.) is deferred to the transform stage
    for maximum flexibility.

    Args:
        force_refetch: If True, refetch all items regardless of existing data
    """
    start_time = time.time()
    http_session = requests.Session()

    page = 1
    total_num_created = 0
    total_num_updated = 0
    total_num_skipped = 0

    logging.info("Starting AIC extraction for public domain artworks")

    while True:
        num_created = 0
        num_updated = 0
        num_skipped = 0

        # Build query parameters - server-side filter for public domain
        query = {
            "query[bool][filter][0][term][is_public_domain]": "true",
            "fields": ",".join(FIELDS),
            "size": LIMIT,  # Search endpoint uses 'size' not 'limit'
            "page": page,
        }

        try:
            data = fetch_raw_data_from_aic_api(query, http_session)
        except requests.RequestException as e:
            logging.error(f"Failed to fetch data at page {page}: {e}")
            break

        items = data.get("items", [])
        total = data.get("total_count", 0)
        total_pages = data.get("total_pages", 0)

        if not items:
            logging.info("No more items to process")
            break

        logging.info(f"Total items matching query: {total}")
        logging.info(f"Processing page {page}/{total_pages} ({len(items)} items)")

        for item in items:
            # Client-side validation
            is_public_domain = item.get("is_public_domain", False)
            image_id = item.get("image_id")
            object_number = item.get("main_reference_number")

            # Defensive check: verify public domain (should be true from server filter)
            if not is_public_domain:
                logging.warning(
                    f"Skipping item with id {item.get('id')} - not public domain (unexpected)"
                )
                num_skipped += 1
                total_num_skipped += 1
                continue

            # Skip items without image_id (required for image loading stage)
            if not image_id:
                num_skipped += 1
                total_num_skipped += 1
                continue

            # Skip items without main_reference_number (our unique identifier)
            if not object_number:
                logging.warning(
                    f"Skipping item with id {item.get('id')} - missing main_reference_number"
                )
                num_skipped += 1
                total_num_skipped += 1
                continue

            created = store_raw_data(
                museum_slug=MUSEUM_SLUG,
                object_number=object_number,
                raw_json=item,
                museum_db_id=str(item.get("id")),
            )

            if created:
                num_created += 1
                total_num_created += 1
            else:
                num_updated += 1
                total_num_updated += 1

        logging.info(
            f"Items created: {num_created}, updated: {num_updated}, skipped (filtered): {num_skipped}"
        )

        # Check if we've processed all pages
        if page >= total_pages:
            logging.info("All pages processed for AIC")
            break

        page += 1
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    logging.info(f"Total items created: {total_num_created}")
    logging.info(f"Total items updated: {total_num_updated}")
    logging.info(f"Total items skipped (filtered out): {total_num_skipped}")
    print(f"Total time taken: {time.time() - start_time:.2f} seconds")
