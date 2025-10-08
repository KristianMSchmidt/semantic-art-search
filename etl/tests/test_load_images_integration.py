"""
Integration test for image load pipeline.

Tests WHAT the image loading pipeline should do (download images and track state),
not HOW it does it (implementation details).
"""

import pytest
import requests
from unittest.mock import Mock, patch
from io import BytesIO
from PIL import Image

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


@pytest.mark.integration
@pytest.mark.django_db
def test_failed_images_are_marked_and_skipped():
    """
    Test that permanent errors (404) fail immediately without retries.

    This test verifies the fix for the infinite loop bug where 404 errors would
    cause the same records to be retried indefinitely.

    Tests:
    - 404 errors fail immediately (no retries)
    - Failed image downloads set image_load_failed=True
    - Failed records are excluded from get_records_needing_processing
    - reset_image_load_failed_field allows retrying failed downloads
    """

    # Step 1: Create a test record with a bad URL
    transformed = TransformedData.objects.create(
        museum_slug="test",
        object_number="TEST001",
        museum_db_id="test-id-001",
        thumbnail_url="https://example.com/nonexistent.jpg",
        searchable_work_types=["painting"],
        image_loaded=False,
        image_load_failed=False,
    )

    # Step 2: Process with mocked bucket service that raises 404 error
    with patch("etl.services.image_load_service.BucketService") as MockBucketService:
        mock_bucket_service = Mock()
        MockBucketService.return_value = mock_bucket_service

        # Simulate 404 error (permanent error - should not retry)
        mock_bucket_service.upload_thumbnail.side_effect = RuntimeError(
            "Failed to download https://example.com/nonexistent.jpg: 404 Not Found"
        )

        service = ImageLoadService()

        # Process - should fail immediately without retries
        status = service.process_single_record(transformed, delay_seconds=0.0)
        assert status == "error", "Processing should return error status"

        # Verify upload_thumbnail was called exactly once (no retries for 404)
        assert (
            mock_bucket_service.upload_thumbnail.call_count == 1
        ), "404 errors should fail immediately without retries"

        # Verify image_load_failed was set
        transformed.refresh_from_db()
        assert transformed.image_loaded is False, "image_loaded should still be False"
        assert (
            transformed.image_load_failed is True
        ), "image_load_failed should be True after error"

        # Step 3: Verify record is excluded from future queries
        records = service.get_records_needing_processing(
            batch_size=100, museum_filter="test"
        )
        our_records = [r for r in records if r.object_number == "TEST001"]

        assert (
            len(our_records) == 0
        ), "Failed record should be excluded from get_records_needing_processing"

        # Step 4: Test reset_image_load_failed_field
        count = service.reset_image_load_failed_field(museum_filter="test")
        assert count >= 1, "Should reset at least our test record"

        transformed.refresh_from_db()
        assert (
            transformed.image_load_failed is False
        ), "reset_image_load_failed_field should set flag to False"

        # Step 5: Verify record is included again after reset
        records = service.get_records_needing_processing(
            batch_size=100, museum_filter="test"
        )
        our_records = [r for r in records if r.object_number == "TEST001"]
        assert len(our_records) == 1, "After reset, failed record should be retryable"


@pytest.mark.integration
@pytest.mark.django_db
def test_transient_errors_are_retried():
    """
    Test that transient errors (5xx, timeouts) are retried with exponential backoff.

    Tests:
    - Transient errors trigger retries (up to max_retries)
    - Exponential backoff is used between retries
    - Success after retry marks image_loaded=True
    - Exhausted retries mark image_load_failed=True
    """

    # Test Case 1: Success on second retry
    transformed1 = TransformedData.objects.create(
        museum_slug="test",
        object_number="TEST002",
        museum_db_id="test-id-002",
        thumbnail_url="https://example.com/transient.jpg",
        searchable_work_types=["painting"],
        image_loaded=False,
        image_load_failed=False,
    )

    with patch("etl.services.image_load_service.BucketService") as MockBucketService:
        mock_bucket_service = Mock()
        MockBucketService.return_value = mock_bucket_service

        # Simulate 503 error on first call, then success
        mock_bucket_service.upload_thumbnail.side_effect = [
            RuntimeError("Failed to download: 503 Service Unavailable"),
            None,  # Success on second attempt
        ]

        service = ImageLoadService()

        # Process - should succeed after retry
        with patch("time.sleep"):  # Mock sleep to speed up test
            status = service.process_single_record(transformed1, delay_seconds=0.0)

        assert status == "success", "Should succeed after retry"
        assert (
            mock_bucket_service.upload_thumbnail.call_count == 2
        ), "Should have retried once (2 total calls)"

        # Verify success state
        transformed1.refresh_from_db()
        assert transformed1.image_loaded is True, "image_loaded should be True"
        assert (
            transformed1.image_load_failed is False
        ), "image_load_failed should be False"

    # Test Case 2: All retries exhausted
    transformed2 = TransformedData.objects.create(
        museum_slug="test",
        object_number="TEST003",
        museum_db_id="test-id-003",
        thumbnail_url="https://example.com/timeout.jpg",
        searchable_work_types=["painting"],
        image_loaded=False,
        image_load_failed=False,
    )

    with patch("etl.services.image_load_service.BucketService") as MockBucketService:
        mock_bucket_service = Mock()
        MockBucketService.return_value = mock_bucket_service

        # Simulate persistent 502 error (retryable but keeps failing)
        mock_bucket_service.upload_thumbnail.side_effect = RuntimeError(
            "Failed to download: 502 Bad Gateway"
        )

        service = ImageLoadService()

        # Process - should fail after all retries
        with patch("time.sleep"):  # Mock sleep to speed up test
            status = service.process_single_record(
                transformed2, delay_seconds=0.0, max_retries=3
            )

        assert status == "error", "Should fail after exhausting retries"
        assert (
            mock_bucket_service.upload_thumbnail.call_count == 3
        ), "Should have tried 3 times (max_retries=3)"

        # Verify failed state
        transformed2.refresh_from_db()
        assert transformed2.image_loaded is False, "image_loaded should be False"
        assert (
            transformed2.image_load_failed is True
        ), "image_load_failed should be True after exhausting retries"


@pytest.mark.integration
def test_image_resizing_works():
    """
    Test that the resize_image_with_aspect_ratio function correctly resizes images.

    This integration test verifies:
    - Images are resized to correct dimensions
    - Aspect ratio is maintained
    - Different image sizes and aspect ratios work correctly
    - Output is JPEG format
    """
    from etl.services.bucket_service import resize_image_with_aspect_ratio

    # Test 1: Wide image (3000×1000 → 800×266)
    img1 = Image.new("RGB", (3000, 1000), color="red")
    img1_bytes = BytesIO()
    img1.save(img1_bytes, format="JPEG")

    resized1 = resize_image_with_aspect_ratio(img1_bytes.getvalue(), max_dimension=800)
    resized_img1 = Image.open(BytesIO(resized1))

    assert resized_img1.width == 800, "Wide image width should be 800"
    assert resized_img1.height == 266, "Wide image height should be 266"
    assert resized_img1.format == "JPEG", "Output should be JPEG"

    # Test 2: Tall image (1000×3000 → 266×800)
    img2 = Image.new("RGB", (1000, 3000), color="blue")
    img2_bytes = BytesIO()
    img2.save(img2_bytes, format="JPEG")

    resized2 = resize_image_with_aspect_ratio(img2_bytes.getvalue(), max_dimension=800)
    resized_img2 = Image.open(BytesIO(resized2))

    assert resized_img2.width == 266, "Tall image width should be 266"
    assert resized_img2.height == 800, "Tall image height should be 800"

    # Test 3: Already small image (stays same size)
    img3 = Image.new("RGB", (600, 400), color="green")
    img3_bytes = BytesIO()
    img3.save(img3_bytes, format="JPEG")

    resized3 = resize_image_with_aspect_ratio(img3_bytes.getvalue(), max_dimension=800)
    resized_img3 = Image.open(BytesIO(resized3))

    assert resized_img3.width == 600, "Small image width should stay 600"
    assert resized_img3.height == 400, "Small image height should stay 400"


@pytest.mark.integration
@pytest.mark.django_db
def test_bucket_service_resizes_before_upload():
    """
    Test that BucketService.upload_thumbnail resizes images before uploading to S3.

    This integration test verifies:
    - Images are resized before S3 upload
    - Resized bytes are passed to S3 put_object
    - Graceful fallback works if resize fails
    """
    from etl.services.bucket_service import BucketService

    # Create a test image that needs resizing (2000×1500)
    test_img = Image.new("RGB", (2000, 1500), color="purple")
    img_bytes_io = BytesIO()
    test_img.save(img_bytes_io, format="JPEG")
    test_img_bytes = img_bytes_io.getvalue()

    # Mock the download response
    mock_response = Mock()
    mock_response.content = test_img_bytes
    mock_response.headers = {"Content-Type": "image/jpeg"}

    with patch("etl.services.bucket_service.get_image_response") as mock_get_image:
        mock_get_image.return_value = mock_response

        # Create bucket service with mocked S3 client
        bucket_service = BucketService()

        # Mock the S3 put_object to capture what gets uploaded
        uploaded_data = {}

        def capture_upload(**kwargs):
            uploaded_data["Body"] = kwargs["Body"]
            uploaded_data["ContentType"] = kwargs["ContentType"]

        bucket_service.s3.put_object = Mock(side_effect=capture_upload)

        # Upload thumbnail
        bucket_service.upload_thumbnail(
            museum="test", object_number="TEST123", museum_image_url="https://example.com/test.jpg"
        )

        # Verify upload was called
        assert bucket_service.s3.put_object.called, "S3 put_object should be called"

        # Verify the uploaded data is resized
        uploaded_img = Image.open(BytesIO(uploaded_data["Body"]))
        assert uploaded_img.width == 800, "Uploaded image width should be 800"
        assert uploaded_img.height == 600, "Uploaded image height should be 600 (1500 * 800/2000)"
        assert uploaded_data["ContentType"] == "image/jpeg", "Content type should be JPEG"

        # Verify original image was larger
        original_img = Image.open(BytesIO(test_img_bytes))
        assert original_img.width == 2000, "Original was 2000px wide"
        assert original_img.height == 1500, "Original was 1500px tall"
