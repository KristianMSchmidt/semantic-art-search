"""
Integration test for AIC extraction pipeline.

Tests WHAT the extraction pipeline should do (fetch and store real museum data),
not HOW it does it (implementation details).
"""

import pytest
import requests

from etl.models import MetaDataRaw
from etl.pipeline.extract.extractors.aic_extractor import (
    BASE_URL,
    FIELDS,
    fetch_raw_data_from_aic_api,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


@pytest.mark.integration
@pytest.mark.django_db
def test_fetch_and_store_single_aic_artwork():
    """
    Test that we can fetch a real AIC artwork from their API and store it correctly.

    This test uses the REAL AIC API (no mocking) to verify the extraction pipeline
    works end-to-end. This catches API changes that would break production.

    Tests:
    - Real API call works (catches API downtime or schema changes)
    - Server-side filtering for public domain works
    - Data is stored in database correctly
    - Idempotency: running twice doesn't create duplicates

    Potential bugs this could catch:
    - AIC API schema changed
    - Search endpoint filter syntax broken
    - Database unique constraint broken
    - Update/create logic broken
    - API client error handling issues
    """

    # Search for a single public domain artwork from AIC
    query = {
        "query[bool][filter][0][term][is_public_domain]": "true",
        "fields": ",".join(FIELDS),
        "size": 1,
        "page": 1,
    }

    http_session = requests.Session()

    # Fetch from real API
    data = fetch_raw_data_from_aic_api(query, http_session, BASE_URL)

    # Verify we got data back
    assert data["total_count"] > 0, "AIC API returned no results"
    assert len(data["items"]) == 1, "Expected exactly 1 item"

    item = data["items"][0]

    # Verify essential fields exist in API response
    assert "main_reference_number" in item, "API response missing main_reference_number"
    assert item["main_reference_number"] is not None, "main_reference_number is None"
    assert "id" in item, "API response missing id"
    assert item["id"] is not None, "id is None"
    assert "is_public_domain" in item, "API response missing is_public_domain"
    assert item["is_public_domain"] is True, "Server filter failed - item not public domain"
    assert "image_id" in item, "API response missing image_id"

    object_number = item["main_reference_number"]
    museum_db_id = str(item["id"])

    # Store in database (first time - should create)
    created_first = store_raw_data(
        museum_slug="aic",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    assert created_first is True, "First store should create a new record"

    # Verify record exists in database
    record = MetaDataRaw.objects.get(museum_slug="aic", object_number=object_number)
    assert record.museum_slug == "aic"
    assert record.object_number == object_number
    assert record.museum_db_id == museum_db_id
    assert isinstance(record.raw_json, dict)
    assert "main_reference_number" in record.raw_json
    assert record.raw_json["is_public_domain"] is True

    # Store again (should update, not create duplicate)
    created_second = store_raw_data(
        museum_slug="aic",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    assert created_second is False, "Second store should update, not create"

    # Verify only one record exists (no duplicates)
    count = MetaDataRaw.objects.filter(
        museum_slug="aic", object_number=object_number
    ).count()
    assert count == 1, "Should have exactly 1 record (no duplicates)"


@pytest.mark.integration
@pytest.mark.django_db
def test_aic_public_domain_filter():
    """
    Test that AIC server-side public domain filter works correctly.

    This test verifies that the Elasticsearch bool filter syntax correctly
    filters for public domain artworks at the API level, ensuring we only
    fetch artworks we're allowed to use.

    Tests:
    - All fetched items have is_public_domain=true
    - Server-side filter is working (not just client-side)
    - Total count represents only public domain works
    """

    query = {
        "query[bool][filter][0][term][is_public_domain]": "true",
        "fields": "id,main_reference_number,is_public_domain",
        "size": 10,
        "page": 1,
    }

    http_session = requests.Session()
    data = fetch_raw_data_from_aic_api(query, http_session, BASE_URL)

    # Verify we got results
    assert data["total_count"] > 0, "AIC API returned no public domain results"
    assert len(data["items"]) > 0, "Expected at least 1 item"

    # Verify ALL items are public domain
    for item in data["items"]:
        assert (
            item.get("is_public_domain") is True
        ), f"Item {item.get('id')} is not public domain - server filter failed"

    # The total_count should be in the tens of thousands (all public domain artworks)
    assert (
        data["total_count"] > 10000
    ), f"Expected >10k public domain works, got {data['total_count']}"


@pytest.mark.integration
@pytest.mark.django_db
def test_aic_required_fields_present():
    """
    Test that all required fields are present in AIC API responses.

    This catches breaking changes in the AIC API where fields we depend on
    are renamed or removed.

    Tests:
    - Required fields for extraction: id, main_reference_number, image_id, is_public_domain
    - Required fields for transformation: title, artist_display, date_start, date_end, classification_titles
    """

    query = {
        "query[bool][filter][0][term][is_public_domain]": "true",
        "fields": ",".join(FIELDS),
        "size": 1,
        "page": 1,
    }

    http_session = requests.Session()
    data = fetch_raw_data_from_aic_api(query, http_session, BASE_URL)

    assert len(data["items"]) > 0, "No items returned"
    item = data["items"][0]

    # Required for extraction
    required_extract_fields = ["id", "main_reference_number", "image_id", "is_public_domain"]
    for field in required_extract_fields:
        assert field in item, f"Missing required extraction field: {field}"
        assert item[field] is not None, f"Field {field} is None"

    # Required for transformation
    required_transform_fields = ["title", "artist_display", "classification_titles"]
    for field in required_transform_fields:
        assert field in item, f"Missing required transformation field: {field}"

    # Optional but expected fields
    expected_fields = ["date_start", "date_end", "date_display", "medium_display"]
    for field in expected_fields:
        assert field in item, f"Missing expected field: {field}"
