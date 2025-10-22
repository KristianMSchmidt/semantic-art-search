import logging
import requests
import time
from typing import Any
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


MUSEUM_SLUG = "aic"
LIMIT = 100  # 100 is maximum allowed by AIC API
BASE_URL = "https://api.artic.edu/api/v1/artworks"  # Listing endpoint (search endpoint has 1K/10K limits)
SLEEP_BETWEEN_REQUESTS = (
    # Be polite to the AIC API
    3  # Seconds (rate limit: 60 req/min, this gives 20 req/min for safety)
)

# Artwork types to include (client-side filtering)
# NB: A complete list of artwork types can be fetched here https://api.artic.edu/api/v1/artwork-types
# We fetch ALL artworks from AIC via listing endpoint, then filter by these types
ALLOWED_ARTWORK_TYPES = {
    "Painting",
    "Drawing and Watercolor",
    "Print",
    "Miniature Painting",
    "Design",
}

# Fields to request from the API
# To not overload the museum API, we only request the fields we know we need.
FIELDS = [
    "id",
    "title",
    "artist_display",
    "date_start",
    "date_end",
    "date_display",
    "main_reference_number",
    "image_id",  # Used to construct IIIF image URLs
    "is_public_domain",
    "artwork_type_title",
    "artist_title",
    "classification_title",
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

    Strategy: Use the /artworks listing endpoint (no pagination limit) to fetch ALL
    artworks, then filter client-side for:
    - Public domain only (is_public_domain=true)
    - Has image_id (required for image loading stage)
    - Artwork type in ALLOWED_ARTWORK_TYPES
    - Has main_reference_number (our unique identifier)

    This avoids the /search endpoint's pagination limitations entirely.

    Args:
        force_refetch: If True, refetch all items regardless of existing data
    """
    start_time = time.time()
    http_session = requests.Session()

    total_num_created = 0
    total_num_updated = 0
    total_num_skipped = 0
    page = 1

    logging.info("Starting AIC extraction using /artworks listing endpoint")
    logging.info(
        f"Filtering for artwork types: {', '.join(sorted(ALLOWED_ARTWORK_TYPES))}"
    )

    while True:
        # Build query parameters for listing endpoint
        query = {
            "fields": ",".join(FIELDS),
            "limit": LIMIT,
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

        if page == 1:
            logging.info(f"Total artworks in AIC collection: {total:,}")
            logging.info(f"Total pages to process: {total_pages:,}")

        logging.info(f"Processing page {page}/{total_pages} ({len(items)} items)")

        page_created = 0
        page_updated = 0
        page_skipped = 0

        for item in items:
            # Client-side filtering
            is_public_domain = item.get("is_public_domain", False)
            image_id = item.get("image_id")
            object_number = item.get("main_reference_number")
            artwork_type_title = item.get("artwork_type_title")

            # Filter 1: Must be public domain
            if not is_public_domain:
                page_skipped += 1
                continue

            # Filter 2: Must have image_id
            if not image_id:
                page_skipped += 1
                continue

            # Filter 3: Must have main_reference_number
            if not object_number:
                page_skipped += 1
                continue

            # Filter 4: Must be in allowed artwork types
            if artwork_type_title not in ALLOWED_ARTWORK_TYPES:
                page_skipped += 1
                continue

            # All filters passed - store the artwork
            created = store_raw_data(
                museum_slug=MUSEUM_SLUG,
                object_number=object_number,
                raw_json=item,
                museum_db_id=str(item.get("id")),
            )

            if created:
                page_created += 1
                total_num_created += 1
            else:
                page_updated += 1
                total_num_updated += 1

        total_num_skipped += page_skipped

        logging.info(
            f"Page {page} complete: created={page_created}, updated={page_updated}, "
            f"skipped={page_skipped} (filtered out)"
        )

        # Check if we've processed all pages
        if page >= total_pages:
            logging.info("All pages processed")
            break

        page += 1
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    logging.info(f"Total items created: {total_num_created}")
    logging.info(f"Total items updated: {total_num_updated}")
    logging.info(f"Total items skipped (filtered out): {total_num_skipped}")
    print(f"Total time taken: {time.time() - start_time:.2f} seconds")
