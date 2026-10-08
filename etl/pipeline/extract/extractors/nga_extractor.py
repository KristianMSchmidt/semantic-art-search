import csv
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator
import requests
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


MUSEUM_SLUG = "nga"

# NGA has no per-object metadata API. Instead, the full collection is published as
# CSV files (CC0) in a GitHub repository, updated daily:
# https://github.com/NationalGalleryOfArt/opendata
BASE_URL = "https://raw.githubusercontent.com/NationalGalleryOfArt/opendata/main/data"
OBJECTS_FILE = "objects.csv"
PUBLISHED_IMAGES_FILE = "published_images.csv"

# Classifications to include. A complete list can be found in the objects.csv
# 'classification' column. We start with paintings only (~2.9k artworks).
# NgaTransformer also supports "Drawing", "Print" and "Index of American Design"
# (watercolor/graphite renderings of American decorative arts, which NGA itself
# classifies as drawings), so these can be added here later (~53k artworks in total).
ALLOWED_CLASSIFICATIONS = {
    "Painting",
}

# Some CSV fields (e.g. provenance text) exceed the default csv field size limit
csv.field_size_limit(sys.maxsize)


def download_csv(file_name: str, dest_dir: Path, base_url: str = BASE_URL) -> Path:
    """Download a CSV file from the NGA open data repository to dest_dir."""
    url = f"{base_url}/{file_name}"
    dest_path = dest_dir / file_name

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
            break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            logging.warning(f"Attempt {attempt + 1} to download {url} failed: {e}. Retrying...")
            time.sleep(2**attempt)  # Exponential backoff

    logging.info(f"Downloaded {url} ({dest_path.stat().st_size / 1e6:.1f} MB)")
    return dest_path


def read_open_access_primary_images(images_path: Path) -> dict[str, dict[str, str]]:
    """
    Read published_images.csv and return the open access primary image per object.

    Returns:
        dict mapping objectid -> image row. If an object has multiple primary
        images, the one with the lowest sequence number is used.
    """
    images: dict[str, dict[str, str]] = {}
    with open(images_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["viewtype"] != "primary" or row["openaccess"] != "1":
                continue
            object_id = row["depictstmsobjectid"]
            existing = images.get(object_id)
            if existing is None or int(row["sequence"] or 0) < int(
                existing["sequence"] or 0
            ):
                images[object_id] = row
    return images


def iter_nga_records(
    objects_path: Path, images_path: Path
) -> Iterator[dict[str, Any]]:
    """
    Join objects.csv with published_images.csv and yield records to store.

    Filters:
    - Classification in ALLOWED_CLASSIFICATIONS
    - Not a virtual object (virtual objects are groupings, not artworks)
    - Has an open access primary image (open access images are public domain)
    - Has an accession number (our unique identifier)

    Each yielded record is the full objects.csv row with the image row nested under "image".
    """
    images = read_open_access_primary_images(images_path)
    logging.info(f"Found {len(images):,} objects with an open access primary image")

    with open(objects_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["classification"] not in ALLOWED_CLASSIFICATIONS:
                continue
            if row["isvirtual"] == "1":
                continue
            if not row["accessionnum"]:
                continue
            image = images.get(row["objectid"])
            if image is None:
                continue
            yield {**row, "image": image}


def store_raw_data_nga(force_refetch: bool = False):
    """
    Download the NGA open data CSV files and store matching artworks as raw data.

    Since NGA publishes its data as complete CSV dumps, every run processes the full
    collection and upserts all records (force_refetch has no effect).

    Args:
        force_refetch: Unused, kept for a consistent extractor interface
    """
    start_time = time.time()
    total_num_created = 0
    total_num_updated = 0
    seen_object_numbers: set[str] = set()

    with tempfile.TemporaryDirectory() as tmp_dir:
        objects_path = download_csv(OBJECTS_FILE, Path(tmp_dir))
        images_path = download_csv(PUBLISHED_IMAGES_FILE, Path(tmp_dir))

        for i, record in enumerate(iter_nga_records(objects_path, images_path), 1):
            object_number = record["accessionnum"]

            # Safeguard: first occurrence wins (accession numbers are unique in practice)
            if object_number in seen_object_numbers:
                logging.warning(f"Skipping duplicate object_number: {object_number}")
                continue
            seen_object_numbers.add(object_number)

            created = store_raw_data(
                museum_slug=MUSEUM_SLUG,
                object_number=object_number,
                raw_json=record,
                museum_db_id=record["objectid"],
            )
            if created:
                total_num_created += 1
            else:
                total_num_updated += 1

            if i % 5000 == 0:
                logging.info(f"Processed {i:,} records")

    logging.info(f"Total items created: {total_num_created}")
    logging.info(f"Total items updated: {total_num_updated}")
    logging.info(f"Total time taken: {time.time() - start_time:.2f} seconds")
