"""
Integration test for SMK transformation pipeline.

Tests WHAT the transformation pipeline should do (transform raw data to standardized format),
not HOW it does it (implementation details).
"""

import pytest
import requests

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.extract.extractors.smk_extractor import (
    BASE_SEARCH_URL,
    fetch_raw_data_from_smk_api,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.pipeline.transform.transform import transform_and_upsert


@pytest.mark.integration
@pytest.mark.django_db
def test_transform_smk_artwork_from_raw_to_transformed():
    """
    Test that we can transform a real SMK artwork from MetaDataRaw to TransformedData.

    This test uses real SMK API data (no mocking) to verify the transformation pipeline
    works end-to-end with actual museum data structures.

    Tests:
    - Fetch real artwork from SMK API
    - Store in MetaDataRaw (extraction step)
    - Transform to TransformedData (transformation step)
    - Required fields are correctly extracted
    - Idempotency: transforming twice doesn't create duplicates

    Potential bugs this could catch:
    - SMK JSON schema changed (breaking field extraction)
    - Transformer not extracting required fields
    - Database unique constraint broken
    - Update/create logic broken
    - Type conversion errors (dates, lists, etc.)
    """

    # Step 1: Fetch real SMK artwork (same as extraction test)
    query = {
        "keys": "*",
        "rows": 1,
        "filters": "[has_image:true],[object_names:maleri],[public_domain:true]",
        "offset": 0,
    }

    http_session = requests.Session()
    data = fetch_raw_data_from_smk_api(query, http_session, BASE_SEARCH_URL)

    assert data["total_count"] > 0, "SMK API returned no results"
    assert len(data["items"]) == 1, "Expected exactly 1 item"

    item = data["items"][0]
    object_number = item["object_number"]
    museum_db_id = item.get("id")

    # Step 2: Store in MetaDataRaw (extraction step)
    store_raw_data(
        museum_slug="smk",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    raw_record = MetaDataRaw.objects.get(museum_slug="smk", object_number=object_number)

    # Step 3: Transform to TransformedData (transformation step)
    status = transform_and_upsert(raw_record)

    assert status == "created", "First transform should create a new record"

    # Step 4: Verify TransformedData has correct fields
    transformed = TransformedData.objects.get(
        museum_slug="smk", object_number=object_number
    )

    # Verify required fields are present and valid
    assert transformed.museum_slug == "smk"
    assert transformed.object_number == object_number
    assert transformed.museum_db_id == museum_db_id
    assert transformed.thumbnail_url is not None, "thumbnail_url is required"
    assert transformed.thumbnail_url.startswith("http"), "thumbnail_url should be a URL"
    assert isinstance(transformed.searchable_work_types, list), "searchable_work_types should be a list"
    assert len(transformed.searchable_work_types) > 0, "searchable_work_types should not be empty"

    # Verify optional fields are present (even if None/empty is valid)
    assert hasattr(transformed, "title")
    assert hasattr(transformed, "work_types")
    assert hasattr(transformed, "artists")
    assert isinstance(transformed.work_types, list)
    assert isinstance(transformed.artists, list)

    # Verify at least one of these fields is populated (sanity check that transformer is working)
    has_data = (
        transformed.title is not None
        or len(transformed.work_types) > 0
        or len(transformed.artists) > 0
        or transformed.production_date_start is not None
        or transformed.period is not None
    )
    assert has_data, "At least one optional field should have data from SMK API"

    # Step 5: Test idempotency - transform again
    status_second = transform_and_upsert(raw_record)

    assert status_second == "updated", "Second transform should update, not create"

    # Verify still only one record exists
    count = TransformedData.objects.filter(
        museum_slug="smk", object_number=object_number
    ).count()
    assert count == 1, "Should have exactly 1 record (no duplicates)"
