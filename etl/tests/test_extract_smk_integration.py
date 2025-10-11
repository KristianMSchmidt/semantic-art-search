"""
Integration test for SMK extraction pipeline.

Tests WHAT the extraction pipeline should do (fetch and store real museum data),
not HOW it does it (implementation details).
"""

import pytest
import requests

from etl.models import MetaDataRaw
from etl.pipeline.extract.extractors.smk_extractor import (
    BASE_SEARCH_URL,
    fetch_raw_data_from_smk_api,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


@pytest.mark.integration
@pytest.mark.django_db
def test_fetch_and_store_single_smk_artwork():
    """
    Test that we can fetch a real SMK artwork from their API and store it correctly.

    This test uses the REAL SMK API (no mocking) to verify the extraction pipeline
    works end-to-end. This catches API changes that would break production.

    Tests:
    - Real API call works (catches API downtime or schema changes)
    - Data is stored in database correctly
    - Idempotency: running twice doesn't create duplicates

    Potential bugs this could catch:
    - SMK API schema changed
    - Database unique constraint broken
    - Update/create logic broken
    - API client error handling issues
    """

    # Search for a single artwork from SMK
    # Using "maleri" (painting) work type as it's common and stable
    query = {
        "keys": "*",
        "rows": 1,
        "filters": "[has_image:true],[object_names:maleri],[public_domain:true]",
        "offset": 0,
    }

    http_session = requests.Session()

    # Fetch from real API
    data = fetch_raw_data_from_smk_api(query, http_session, BASE_SEARCH_URL)

    # Verify we got data back
    assert data["total_count"] > 0, "SMK API returned no results"
    assert len(data["items"]) == 1, "Expected exactly 1 item"

    item = data["items"][0]

    # Verify essential fields exist in API response
    assert "object_number" in item, "API response missing object_number"
    assert item["object_number"] is not None, "object_number is None"

    object_number = item["object_number"]
    museum_db_id = item.get("id")

    # Store in database (first time - should create)
    created_first = store_raw_data(
        museum_slug="smk",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    assert created_first is True, "First store should create a new record"

    # Verify record exists in database
    record = MetaDataRaw.objects.get(museum_slug="smk", object_number=object_number)
    assert record.museum_slug == "smk"
    assert record.object_number == object_number
    assert record.museum_db_id == museum_db_id
    assert isinstance(record.raw_json, dict)
    assert "object_number" in record.raw_json

    # Store again (should update, not create duplicate)
    created_second = store_raw_data(
        museum_slug="smk",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    assert created_second is False, "Second store should update, not create"

    # Verify only one record exists (no duplicates)
    count = MetaDataRaw.objects.filter(
        museum_slug="smk", object_number=object_number
    ).count()
    assert count == 1, "Should have exactly 1 record (no duplicates)"
