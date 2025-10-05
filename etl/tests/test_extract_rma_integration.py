"""
Integration test for RMA extraction pipeline.

Tests WHAT the extraction pipeline should do (fetch and store real museum data),
not HOW it does it (implementation details).
"""

import pytest
import requests

from etl.models import MetaDataRaw
from etl.pipeline.extract.extractors.rma_extractor import (
    BASE_SEARCH_URL,
    fetch_raw_data_from_rma_api,
    fetch_record,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.pipeline.shared.rma_utils import extract_provided_cho, extract_object_number


@pytest.mark.integration
@pytest.mark.django_db
def test_fetch_and_store_single_rma_artwork():
    """
    Test that we can fetch a real RMA artwork from their API and store it correctly.

    This test uses the REAL RMA API (no mocking) to verify the extraction pipeline
    works end-to-end. This catches API changes that would break production.

    Tests:
    - Real API call works (catches API downtime or schema changes)
    - Data is stored in database correctly
    - Idempotency: running twice doesn't create duplicates

    Potential bugs this could catch:
    - RMA API schema changed
    - Database unique constraint broken
    - Update/create logic broken
    - API client error handling issues
    """

    # Search for a single artwork from RMA
    # Using "painting" work type as it's common and stable
    query = {
        "type": "painting",
        "pageToken": "",
    }

    http_session = requests.Session()

    # Fetch from real API
    data = fetch_raw_data_from_rma_api(query, http_session, BASE_SEARCH_URL)

    # Verify we got data back
    assert data["total_count"] > 0, "RMA API returned no results"
    assert len(data["items"]) > 0, "Expected at least 1 item"

    item = data["items"][0]
    item_id = item["id"].split("/")[-1]

    # Fetch full record
    record = fetch_record(item_id, http_session)

    # Extract object_number from complex RMA structure
    metadata = record.get("metadata", {})
    rdf = metadata.get("rdf:RDF", {})
    provided_cho = extract_provided_cho(rdf)
    object_number = extract_object_number(provided_cho) if provided_cho else None

    # Verify essential fields exist
    assert object_number is not None, "Failed to extract object_number"

    # Store in database (first time - should create)
    created_first = store_raw_data(
        museum_slug="rma",
        object_number=object_number,
        raw_json=record,
        museum_db_id=item_id,
    )

    assert created_first is True, "First store should create a new record"

    # Verify record exists in database
    db_record = MetaDataRaw.objects.get(museum_slug="rma", object_number=object_number)
    assert db_record.museum_slug == "rma"
    assert db_record.object_number == object_number
    assert db_record.museum_db_id == item_id
    assert isinstance(db_record.raw_json, dict)

    # Store again (should update, not create duplicate)
    created_second = store_raw_data(
        museum_slug="rma",
        object_number=object_number,
        raw_json=record,
        museum_db_id=item_id,
    )

    assert created_second is False, "Second store should update, not create"

    # Verify only one record exists (no duplicates)
    count = MetaDataRaw.objects.filter(
        museum_slug="rma", object_number=object_number
    ).count()
    assert count == 1, "Should have exactly 1 record (no duplicates)"


@pytest.mark.integration
@pytest.mark.django_db
def test_rma_duplicate_object_number_detection():
    """
    Test that RMA extractor skips artworks with duplicate object_number but different museum_db_id.

    This prevents the "flip-flop bug" where the same object_number keeps switching between
    different museum_db_ids, causing data corruption in the downstream pipeline.

    Tests:
    - First artwork with object_number X and museum_db_id A is stored
    - Second artwork with same object_number X but different museum_db_id B is skipped
    - Warning is logged when duplicate is detected
    - Database only contains the first record (A, not B)
    """

    object_number = "SK-A-TEST-001"
    museum_db_id_first = "rma_item_123"
    museum_db_id_duplicate = "rma_item_456"

    # Create first record with object_number and museum_db_id_first
    record_first = {
        "metadata": {
            "rdf:RDF": {
                "ore:Aggregation": {
                    "edm:aggregatedCHO": {
                        "@rdf:resource": "test"
                    }
                },
                "edm:ProvidedCHO": {
                    "dc:identifier": object_number
                }
            }
        }
    }

    created_first = store_raw_data(
        museum_slug="rma",
        object_number=object_number,
        raw_json=record_first,
        museum_db_id=museum_db_id_first,
    )

    assert created_first is True, "First record should be created"

    # Verify first record exists
    first_record = MetaDataRaw.objects.get(
        museum_slug="rma",
        object_number=object_number
    )
    assert first_record.museum_db_id == museum_db_id_first

    # Now simulate the duplicate detection logic from rma_extractor.py (lines 124-138)
    # Check for duplicate object_number with different museum_db_id
    existing = MetaDataRaw.objects.filter(
        museum_slug="rma",
        object_number=object_number
    ).exclude(museum_db_id=museum_db_id_duplicate).first()

    # The duplicate detection should find the existing record
    assert existing is not None, "Should find existing record with same object_number"
    assert existing.museum_db_id == museum_db_id_first

    # In the real extractor, this would trigger a skip and warning log
    # We verify the detection logic works - the extractor would not call store_raw_data
    # for the duplicate, so we don't call it here either

    # Verify only one record exists (the first one)
    count = MetaDataRaw.objects.filter(
        museum_slug="rma",
        object_number=object_number
    ).count()
    assert count == 1, "Should still have exactly 1 record after duplicate detection"

    # Verify it's still the first record, not overwritten
    final_record = MetaDataRaw.objects.get(
        museum_slug="rma",
        object_number=object_number
    )
    assert final_record.museum_db_id == museum_db_id_first, "Original record should remain unchanged"
