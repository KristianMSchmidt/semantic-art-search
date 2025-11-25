"""
Ad-hoc script to update payloads in existing Qdrant collection.

PURPOSE:
--------
This script allows you to modify Qdrant payload fields WITHOUT rerunning the entire
ETL pipeline. This is useful when you need to:
- Add new payload fields to existing points
- Fix/update existing payload field values
- Change payload structure across all artworks

WHEN TO USE THIS VS ETL PIPELINE:
---------------------------------
Use this script when:
- You only need to modify payload metadata (not vectors)
- You want to avoid expensive operations (image downloads, embedding generation)
- You need quick fixes to payload structure/values

Use ETL pipeline when:
- You need to recalculate embeddings (vectors changed)
- You're adding new artworks from scratch
- You need full data refresh from museum APIs

EXAMPLE USE CASES:
-----------------
1. Add new field across all artworks:
   - Add 'credit_line' field to all MET artworks

2. Fix formatting issues:
   - Adjust thumbnail URL format
   - Normalize artist name formatting

3. Update derived fields:
   - Recalculate searchable_work_types from work_types
   - Update title display format

USAGE:
------
1. Modify the adhoc_update_payload() function with your update logic
2. Set the collection_name at bottom of file
3. Run with dry_run=True first to preview changes
4. Set dry_run=False to apply changes
5. Run: make update-payloads

SAFETY:
-------
- Always runs in dry_run mode by default
- Test on a small batch first by limiting the loop iterations
- Consider backing up your collection before running
"""

import logging
import os
import sys
import django

# Add project root to Python path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

# Set up Django environment before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoconfig.settings")
django.setup()

from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.config import config
from etl.models import TransformedData


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def adhoc_update_payload(old_payload: dict) -> dict:
    """
    Define your custom payload update logic here.

    Args:
        old_payload: The existing payload dict from Qdrant

    Returns:
        The updated payload dict

    Example:
        # Add a new field
        new_payload = old_payload.copy()
        new_payload["credit_line"] = "Museum Purchase"
        return new_payload

        # Update existing field
        new_payload = old_payload.copy()
        new_payload["title"] = new_payload["title"].upper()
        return new_payload
    """
    new_payload = old_payload.copy()

    ##### MODIFY THIS SECTION WITH YOUR UPDATE LOGIC #####
    # Add new "artists" field (list) from TransformedData (source of truth)
    # Keep old "artist" field for safety
    museum_slug = old_payload.get("museum")
    object_number = old_payload.get("object_number")

    if not museum_slug or not object_number:
        raise ValueError("Payload missing museum or object_number")

    # Look up the TransformedData record (fail hard if not found)
    try:
        record = TransformedData.objects.get(
            museum_slug=museum_slug, object_number=object_number
        )
        # Add new "artists" field with list from TransformedData
        new_payload["artists"] = record.artist
        # print(f"Updated {museum_slug}:{object_number} artists: {record.artist}")
        print(record.artist)
    except TransformedData.DoesNotExist:
        print(f"TransformedData record not found for {museum_slug}:{object_number}")
        raise
    #######################################################

    return new_payload


def main(
    collection_name: str,
    batch_size: int = 1000,
    dry_run: bool = True,
) -> None:
    """
    Update payload fields using Qdrant's efficient set_payload() method.

    This method only transfers payload data (not vectors), making it fast and efficient.

    Args:
        collection_name: Name of the Qdrant collection
        batch_size: Number of points to process per batch
        dry_run: If True, only shows what would be updated (no actual changes)
    """
    qdrant_service = QdrantService(collection_name=collection_name)
    next_page_token = None
    num_points = 0

    logging.info(
        f"Starting payload update on collection '{collection_name}' - dry_run={dry_run}"
    )

    while True:
        # Fetch points (no vectors needed - more efficient!)
        points, next_page_token = qdrant_service.fetch_points(
            next_page_token,
            limit=batch_size,
            with_vectors=False,
            with_payload=True,
        )

        # Process each point
        for point in points:
            if not point.payload:
                logging.warning(f"Point {point.id} has missing payload")
                continue

            new_payload = adhoc_update_payload(point.payload)

            if not dry_run:
                # Use set_payload for efficient payload-only updates
                qdrant_service.qdrant_client.set_payload(
                    collection_name=collection_name,
                    payload=new_payload,
                    points=[point.id],  # type: ignore
                )

        num_points += len(points)
        logging.info(f"Processed {num_points} points so far...")

        if next_page_token is None:  # No more points left
            break

    if dry_run:
        logging.info(
            f"DRY RUN complete: Would have updated {num_points} points. "
            f"Set dry_run=False to apply changes."
        )
    else:
        logging.info(
            f"Successfully updated {num_points} points in collection {collection_name}"
        )


if __name__ == "__main__":
    # Choose your collection
    # collection_name = config.qdrant_collection_name_etl
    collection_name = config.qdrant_collection_name_app

    confirmation = input(
        f"Are you sure you want to update payloads in collection '{collection_name}'? (yes/no): "
    )
    if confirmation.lower() != "yes":
        logging.info("Operation cancelled by user.")
        exit(0)

    # Run with dry_run=True first to preview changes
    # main(collection_name=collection_name, batch_size=1000, dry_run=True)

    # Once you're confident, set dry_run=False to apply changes
    main(collection_name=collection_name, batch_size=1000, dry_run=False)

    pass
