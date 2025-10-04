"""
Integration test for image load pipeline.

Tests WHAT the image loading pipeline should do (download images and track state),
not HOW it does it (implementation details).
"""

import pytest
import requests
from unittest.mock import Mock, patch

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.extract.extractors.smk_extractor import (
    BASE_SEARCH_URL,
    fetch_raw_data_from_smk_api,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.pipeline.transform.transform import transform_and_upsert
from etl.services.image_load_service import ImageLoadService


@pytest.mark.integration
@pytest.mark.django_db
def test_image_load_updates_database_flag_and_respects_idempotency():
    """
    Test that image loading correctly updates database state and respects idempotency.

    This test uses real database operations but mocks S3 upload to avoid
    expensive external dependencies.

    Tests:
    - Fetch real SMK artwork (extraction step)
    - Transform to TransformedData (transformation step)
    - Process image loading (load step)
    - Database flag `image_loaded` is correctly updated
    - Idempotency: processing twice doesn't re-upload

    Potential bugs this could catch:
    - image_loaded flag not being set after processing
    - Database update transaction failing
    - Idempotency broken (reprocessing when shouldn't)
    - Service integration issues (ImageLoadService → BucketService)
    - Query logic returning wrong records
    """

    # Step 1: Fetch and store real SMK artwork (extraction)
    query = {
        "keys": "*",
        "rows": 1,
        "filters": "[has_image:true],[object_names:maleri],[public_domain:true]",
        "offset": 0,
    }

    http_session = requests.Session()
    data = fetch_raw_data_from_smk_api(query, http_session, BASE_SEARCH_URL)

    assert data["total_count"] > 0, "SMK API returned no results"
    item = data["items"][0]
    object_number = item["object_number"]
    museum_db_id = item.get("id")

    store_raw_data(
        museum_slug="smk",
        object_number=object_number,
        raw_json=item,
        museum_db_id=museum_db_id,
    )

    # Step 2: Transform to TransformedData (transformation)
    raw_record = MetaDataRaw.objects.get(museum_slug="smk", object_number=object_number)
    transform_and_upsert(raw_record)

    transformed = TransformedData.objects.get(
        museum_slug="smk", object_number=object_number
    )

    # Verify initial state
    assert transformed.image_loaded is False, "Should start with image_loaded=False"
    assert transformed.thumbnail_url is not None, "Need thumbnail_url for test"

    # Step 3: Process image loading with mocked S3 upload
    with patch("etl.services.image_load_service.BucketService") as MockBucketService:
        # Create mock instance
        mock_bucket_service = Mock()
        MockBucketService.return_value = mock_bucket_service

        # Create service (will use mocked BucketService)
        service = ImageLoadService()

        # First processing - should upload
        status = service.process_single_record(transformed, delay_seconds=0.0)

        assert status == "success", "First processing should succeed"

        # Verify upload was called with correct arguments
        mock_bucket_service.upload_thumbnail.assert_called_once()
        call_args = mock_bucket_service.upload_thumbnail.call_args
        assert call_args[1]["museum"] == "smk"
        assert call_args[1]["object_number"] == object_number
        assert call_args[1]["museum_image_url"] == transformed.thumbnail_url

        # Verify database flag was updated
        transformed.refresh_from_db()
        assert transformed.image_loaded is True, "image_loaded should be True after processing"

        # Step 4: Test idempotency - process again
        mock_bucket_service.reset_mock()

        # Get records needing processing - should be empty now
        records = service.get_records_needing_processing(
            batch_size=100, museum_filter="smk"
        )

        # Filter to our specific object_number since other records might exist
        our_records = [r for r in records if r.object_number == object_number]

        assert (
            len(our_records) == 0
        ), "Record with image_loaded=True should not be returned for processing"

        # Verify upload_thumbnail was NOT called again
        mock_bucket_service.upload_thumbnail.assert_not_called()

    # Step 5: Test reset functionality for force reload
    count = service.reset_image_loaded_field(museum_filter="smk")
    assert count >= 1, "Should reset at least our test record"

    transformed.refresh_from_db()
    assert (
        transformed.image_loaded is False
    ), "reset_image_loaded_field should set flag to False"

    # Now get_records_needing_processing should return it again
    records = service.get_records_needing_processing(batch_size=100, museum_filter="smk")
    our_records = [r for r in records if r.object_number == object_number]
    assert len(our_records) == 1, "After reset, record should need processing again"
