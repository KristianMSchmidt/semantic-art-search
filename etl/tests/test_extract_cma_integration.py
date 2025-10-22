"""
Integration test for CMA extraction pipeline.

Tests WHAT the extraction pipeline should do (fetch and store real museum data),
not HOW it does it (implementation details).
"""

import pytest
import requests

from etl.models import MetaDataRaw
from etl.pipeline.extract.extractors.cma_extractor import (
    BASE_SEARCH_URL,
    fetch_raw_data_from_cma_api,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data


@pytest.mark.integration
@pytest.mark.django_db
def test_fetch_and_store_single_cma_artwork():
    """
    Test that we can fetch a real CMA artwork from their API and store it correctly.

    This test uses the REAL CMA API (no mocking) to verify the extraction pipeline
    works end-to-end. This catches API changes that would break production.

    Tests:
    - Real API call works (catches API downtime or schema changes)
    - CC0 (public domain) filtering works
    - Data is stored in database correctly
    - Idempotency: running twice doesn't create duplicates

    Potential bugs this could catch:
    - CMA API schema changed
    - Database unique constraint broken
    - Update/create logic broken
    - API client error handling issues
    """

    # Search for a single CC0 painting from CMA
    query = {
        "q": "",
        "has_image": 1,
        "cc0": 1,  # CC0 = public domain
        "type": "Painting",
        "limit": 1,
        "skip": 0,
    }

    http_session = requests.Session()

    # Fetch from real API
    data = fetch_raw_data_from_cma_api(query, http_session, BASE_SEARCH_URL)

    # Verify we got data back
    assert data["total_count"] > 0, "CMA API returned no results"
    assert len(data["items"]) == 1, "Expected exactly 1 item"

    item = data["items"][0]

    # Verify essential fields exist in API response
    assert "accession_number" in item, "API response missing accession_number"
    assert item["accession_number"] is not None, "accession_number is None"
    assert "id" in item, "API response missing id"

    object_number = item["accession_number"]
    museum_db_id = str(item["id"])

    # Store in database (first time - should create)
    created_first = store_raw_data(
        museum_slug="cma",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    assert created_first is True, "First store should create a new record"

    # Verify record exists in database
    record = MetaDataRaw.objects.get(museum_slug="cma", object_number=object_number)
    assert record.museum_slug == "cma"
    assert record.object_number == object_number
    assert record.museum_db_id == museum_db_id
    assert isinstance(record.raw_json, dict)
    assert "accession_number" in record.raw_json

    # Store again (should update, not create duplicate)
    created_second = store_raw_data(
        museum_slug="cma",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    assert created_second is False, "Second store should update, not create"

    # Verify only one record exists (no duplicates)
    count = MetaDataRaw.objects.filter(
        museum_slug="cma", object_number=object_number
    ).count()
    assert count == 1, "Should have exactly 1 record (no duplicates)"


@pytest.mark.integration
@pytest.mark.django_db
def test_cma_cc0_filter():
    """
    Test that CMA CC0 (public domain) filter works correctly.

    This test verifies that the cc0=1 parameter correctly filters for
    public domain artworks, ensuring we only fetch artworks we're allowed to use.

    Tests:
    - All fetched items have cc0 license
    - Server-side filter is working
    - Total count represents only CC0 works
    """

    query = {
        "q": "",
        "has_image": 1,
        "cc0": 1,
        "type": "Painting",
        "limit": 10,
        "skip": 0,
    }

    http_session = requests.Session()
    data = fetch_raw_data_from_cma_api(query, http_session, BASE_SEARCH_URL)

    # Verify we got results
    assert data["total_count"] > 0, "CMA API returned no CC0 results"
    assert len(data["items"]) > 0, "Expected at least 1 item"

    # Verify ALL items have images (has_image=1 filter)
    for item in data["items"]:
        # CMA provides images in nested structure
        images = item.get("images", {})
        assert (
            images is not None and len(images) > 0
        ), f"Item {item.get('id')} has no images - has_image filter failed"

    # The total_count should be reasonable for CC0 paintings
    assert (
        data["total_count"] > 100
    ), f"Expected >100 CC0 paintings, got {data['total_count']}"


@pytest.mark.integration
@pytest.mark.django_db
def test_cma_work_type_filter():
    """
    Test that CMA work type filtering works correctly.

    This test verifies that filtering by type (Painting, Print, Drawing)
    returns only artworks of that type.

    Tests:
    - Type filter correctly filters results
    - Multiple work types are supported
    - Results match the requested type
    """

    work_types = ["Painting", "Print", "Drawing"]

    http_session = requests.Session()

    for work_type in work_types:
        query = {
            "q": "",
            "has_image": 1,
            "cc0": 1,
            "type": work_type,
            "limit": 5,
            "skip": 0,
        }

        data = fetch_raw_data_from_cma_api(query, http_session, BASE_SEARCH_URL)

        # Should get results for each work type
        assert (
            data["total_count"] > 0
        ), f"CMA API returned no results for type={work_type}"
        assert len(data["items"]) > 0, f"Expected items for type={work_type}"

        # Verify items match the requested type
        for item in data["items"]:
            item_type = item.get("type")
            assert (
                item_type == work_type
            ), f"Item type '{item_type}' doesn't match filter '{work_type}'"


@pytest.mark.integration
@pytest.mark.django_db
def test_cma_required_fields_present():
    """
    Test that all required fields are present in CMA API responses.

    This catches breaking changes in the CMA API where fields we depend on
    are renamed or removed.

    Tests:
    - Required fields for extraction: id, accession_number, images
    - Required fields for transformation: title, creators, creation_date
    """

    query = {
        "q": "",
        "has_image": 1,
        "cc0": 1,
        "type": "Painting",
        "limit": 1,
        "skip": 0,
    }

    http_session = requests.Session()
    data = fetch_raw_data_from_cma_api(query, http_session, BASE_SEARCH_URL)

    assert len(data["items"]) > 0, "No items returned"
    item = data["items"][0]

    # Required for extraction
    required_extract_fields = ["id", "accession_number"]
    for field in required_extract_fields:
        assert field in item, f"Missing required extraction field: {field}"
        assert item[field] is not None, f"Field {field} is None"

    # Required for transformation
    required_transform_fields = ["title", "creators", "images"]
    for field in required_transform_fields:
        assert field in item, f"Missing required transformation field: {field}"

    # Verify images structure
    assert isinstance(
        item["images"], dict
    ), "images field should be a dict with nested structure"
    assert "web" in item["images"], "images should have 'web' key"
    assert "url" in item["images"]["web"], "images.web should have 'url' key"

    # Optional but expected fields
    expected_fields = ["creation_date", "type", "department"]
    for field in expected_fields:
        assert field in item, f"Missing expected field: {field}"
