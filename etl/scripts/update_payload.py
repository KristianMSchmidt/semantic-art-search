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
    # Delete the old "artist" field (replaced by "artists" list)
    if "artists" in new_payload:
        if "artist" in new_payload:
            del new_payload["artist"]
    else:
        breakpoint()
    #######################################################

    return new_payload


def main_upsert_bulk(
    collection_name: str,
    batch_size: int = 500,
    dry_run: bool = True,
):
    qdrant = QdrantService(collection_name).qdrant_client
    next_offset = None
    total_processed = 0
    total_updated = 0
    total_unchanged = 0

    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            limit=batch_size,
            with_vectors=True,
            with_payload=True,
            offset=next_offset,
        )

        if not points:
            break

        upserts = []
        batch_updated = 0
        batch_unchanged = 0

        for p in points:
            assert p.payload is not None
            final_payload = adhoc_update_payload(p.payload)
            assert final_payload

            # Only upsert if payload changed
            if final_payload != p.payload:
                upserts.append(
                    {
                        "id": p.id,
                        "vector": p.vector,  # all 4 vectors, unchanged
                        "payload": final_payload,
                    }
                )
                batch_updated += 1
            else:
                batch_unchanged += 1

        if not dry_run and upserts:
            qdrant.upsert(
                collection_name=collection_name,
                points=upserts,
            )

        total_processed += len(points)
        total_updated += batch_updated
        total_unchanged += batch_unchanged

        logging.info(
            f"Batch: {batch_unchanged} unchanged, {batch_updated} updated. "
            f"Total: {total_processed} processed, {total_updated} updated"
        )

        if next_offset is None:
            break

    logging.info(
        f"Summary: {total_processed} total processed, "
        f"{total_updated} updated, {total_unchanged} unchanged"
    )


if __name__ == "__main__":
    collection_name = "artworks_prod_v1"

    confirmation = input(
        f"Are you sure you want to update payloads in collection '{collection_name}'? (yes/no): "
    )

    if confirmation.lower() != "yes":
        logging.info("Operation cancelled by user.")
        exit(0)

    DRY_RUN = False
    main_upsert_bulk(collection_name=collection_name, batch_size=50, dry_run=DRY_RUN)
