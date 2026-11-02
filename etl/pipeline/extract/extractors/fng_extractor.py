import gzip
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator, TextIO

import requests
import urllib3

from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


MUSEUM_SLUG = "fng"

# The Finnish National Gallery (Ateneum, Sinebrychoff, Kiasma) publishes its whole
# collection as one JSON dump (CC0 metadata, CC0 images), no API key needed:
# https://kokoelma.kansallisgalleria.fi/api/swagger
# The dump is ~29 MB gzipped, ~275 MB of JSON (~89k objects), so it is parsed as a stream.
DUMP_URL = "https://kokoelma.kansallisgalleria.fi/api/v1/objects"

# Classifications (English names) to include. An object is included if it has any of
# them. Prints and drawings are left out on purpose: about a third of the prints are
# photographed with a colour chart and inventory labels in the frame (which skews
# colourfulness and visual similarity), and most drawings are faint pencil studies.
# Sculpture is left out until there is a searchable "sculpture" work type.
ALLOWED_CLASSIFICATIONS = {
    "painting",
    "miniature",
    "Japanese woodblock print",
}

# Sketchbooks (and their pages) are excluded even if classified as e.g. drawing/painting
EXCLUDED_CLASSIFICATIONS = {
    "sketch book",
    "sketch pad",
}

# Only standalone artworks. The dump also holds sketchbook pages ("part of a work"),
# letters, photos and archive material.
ARTWORK_CATEGORY_ID = "artwork"
ARTWORK_CATEGORY_NAME = "artwork"

OPEN_LICENSE = "CC0"

# No single object is anywhere near this size; a buffer this large without a complete
# item means the dump is malformed, so fail instead of buffering the whole file
MAX_ITEM_CHARS = 50_000_000


def download_dump(dest_dir: Path, url: str = DUMP_URL) -> Path:
    """Download the full collection dump (gzipped JSON) to dest_dir, as stored by the server."""
    dest_path = dest_dir / "objects.json.gz"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(
                url, stream=True, timeout=120, headers={"Accept-Encoding": "gzip"}
            ) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    # Keep the bytes as sent (gzip), so the file stays small on disk
                    for chunk in response.raw.stream(1024 * 1024, decode_content=False):
                        f.write(chunk)
            break
        # The body is read via response.raw, whose errors (read timeouts, dropped
        # connections) come from urllib3 and are not wrapped by requests
        except (requests.RequestException, urllib3.exceptions.HTTPError) as e:
            if attempt == max_retries - 1:
                raise
            logging.warning(f"Attempt {attempt + 1} to download {url} failed: {e}. Retrying...")
            time.sleep(2**attempt)  # Exponential backoff

    logging.info(f"Downloaded {url} ({dest_path.stat().st_size / 1e6:.1f} MB)")
    return dest_path


def open_dump(path: Path) -> TextIO:
    """Open the dump as text, whether or not it is gzipped."""
    with open(path, "rb") as f:
        is_gzip = f.read(2) == b"\x1f\x8b"
    if is_gzip:
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def iter_json_array(f: TextIO, chunk_size: int = 1024 * 1024) -> Iterator[Any]:
    """
    Yield the items of a top-level JSON array one at a time.

    Loading the whole dump with json.load takes ~1.4 GB of memory; this keeps only
    one chunk plus the current item in memory.
    """
    decoder = json.JSONDecoder()
    buffer = ""
    pos = 0
    started = False
    eof = False

    while True:
        # Skip whitespace and separators between items
        while pos < len(buffer) and buffer[pos] in " \t\r\n,":
            pos += 1
        if not started and pos < len(buffer):
            if buffer[pos] != "[":
                raise ValueError("Expected a JSON array")
            started = True
            pos += 1
            continue
        if started and pos < len(buffer) and buffer[pos] == "]":
            return
        if pos < len(buffer):
            try:
                item, end = decoder.raw_decode(buffer, pos)
            except json.JSONDecodeError:
                if eof:
                    raise
                item = None  # Item cut off at the chunk boundary: read more
            else:
                # Only accept the item if a separator follows: a number cut off at
                # the chunk boundary ("1." of "1.5") also decodes, but too early
                after = end
                while after < len(buffer) and buffer[after] in " \t\r\n":
                    after += 1
                if after < len(buffer) and buffer[after] in ",]":
                    yield item
                    pos = after
                    continue
                if after < len(buffer) and eof:
                    raise ValueError(f"Unexpected character after item: {buffer[after]!r}")
        if eof:
            raise ValueError("Unexpected end of JSON array")
        if len(buffer) - pos > MAX_ITEM_CHARS:
            raise ValueError(f"No complete JSON item in {MAX_ITEM_CHARS:,} characters")
        chunk = f.read(chunk_size)
        if not chunk:
            eof = True
        buffer = buffer[pos:] + chunk
        pos = 0


def get_classifications(obj: dict) -> set[str]:
    """English classification names of an object, e.g. {"painting", "miniature"}."""
    return {c["en"] for c in obj.get("classifications") or [] if c.get("en")}


def get_open_image(obj: dict) -> dict | None:
    """
    The CC0 image to use for an object: its display image if it has one, else the first.
    """
    images = [m for m in obj.get("multimedia") or [] if m.get("license") == OPEN_LICENSE]
    if not images:
        return None
    display_images = [m for m in images if m.get("isRiaDisplayImage")]
    return (display_images or images)[0]


def is_eligible(obj: dict) -> bool:
    """
    Whether an object should be included:
    - A standalone artwork (not a sketchbook page, letter, photo or archive item)
    - Classified as one of ALLOWED_CLASSIFICATIONS, and not as a sketchbook
    - Has a CC0 image (in-copyright works have no image in the dump)
    - Has an inventory number (our unique public identifier)
    """
    category = obj.get("category") or {}
    if category.get("categoryId") != ARTWORK_CATEGORY_ID:
        return False
    if category.get("en") != ARTWORK_CATEGORY_NAME:
        return False
    classifications = get_classifications(obj)
    if not classifications & ALLOWED_CLASSIFICATIONS:
        return False
    if classifications & EXCLUDED_CLASSIFICATIONS:
        return False
    if not (obj.get("inventoryNumber") or "").strip():
        return False
    return get_open_image(obj) is not None


def iter_fng_records(dump_path: Path) -> Iterator[dict[str, Any]]:
    """
    Yield eligible objects from the dump, with the chosen image under "image".

    The full "multimedia" list is dropped, since only the chosen image is used.
    """
    with open_dump(dump_path) as f:
        for obj in iter_json_array(f):
            if is_eligible(obj):
                image = get_open_image(obj)
                record = {k: v for k, v in obj.items() if k != "multimedia"}
                yield {**record, "image": image}


def store_raw_data_fng(force_refetch: bool = False):
    """
    Download the Finnish National Gallery dump and store matching artworks as raw data.

    Since the data is a complete dump, every run processes the full collection and
    upserts all records (force_refetch has no effect).

    Args:
        force_refetch: Unused, kept for a consistent extractor interface
    """
    start_time = time.time()
    total_num_created = 0
    total_num_updated = 0
    seen_object_numbers: set[str] = set()

    with tempfile.TemporaryDirectory() as tmp_dir:
        dump_path = download_dump(Path(tmp_dir))

        for i, record in enumerate(iter_fng_records(dump_path), 1):
            object_number = record["inventoryNumber"].strip()

            # Inventory numbers are unique among the included artworks in practice;
            # first occurrence wins if that ever changes
            if object_number in seen_object_numbers:
                logging.warning(f"Skipping duplicate object_number: {object_number}")
                continue
            seen_object_numbers.add(object_number)

            created = store_raw_data(
                museum_slug=MUSEUM_SLUG,
                object_number=object_number,
                raw_json=record,
                museum_db_id=str(record["objectId"]),
            )
            if created:
                total_num_created += 1
            else:
                total_num_updated += 1

            if i % 1000 == 0:
                logging.info(f"Processed {i:,} records")

    logging.info(f"Total items created: {total_num_created}")
    logging.info(f"Total items updated: {total_num_updated}")
    logging.info(f"Total time taken: {time.time() - start_time:.2f} seconds")
