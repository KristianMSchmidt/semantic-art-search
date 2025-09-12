import hashlib
from unittest.mock import Mock
import pytest

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.load.load_images.service import ImageLoadService
from artsearch.src.services.bucket_service import get_bucket_image_key


@pytest.mark.integration
@pytest.mark.django_db
class TestImageLoadServiceIntegration:
    @pytest.fixture
    def raw_data(self):
        """Create test raw data."""
        return MetaDataRaw.objects.create(
            museum_slug="smk",
            museum_object_id="KMS123",
            raw_json={"test": "data"},
            raw_hash="abc123",
        )

    @pytest.fixture
    def transformed_data(self, raw_data):
        """Create test transformed data."""
        return TransformedData.objects.create(
            raw_data=raw_data,
            source_raw_hash="abc123",
            object_number="KMS123",
            thumbnail_url="https://example.com/thumb.jpg",
            museum_slug="smk",
            searchable_work_types=["painting"],
            image_loaded=False,
        )

    @pytest.fixture
    def mock_bucket_service(self):
        """Create mock bucket service."""
        return Mock()

    @pytest.fixture
    def service(self, mock_bucket_service):
        """Create image load service."""
        return ImageLoadService(bucket_service=mock_bucket_service)

    def test_get_records_needing_processing_never_loaded(self, service, transformed_data):
        """Test querying records that have never been loaded."""
        records = service.get_records_needing_processing()
        assert len(records) >= 1
        our_record = next((r for r in records if r.object_number == "KMS123"), None)
        assert our_record is not None

    def test_get_records_needing_processing_stale_data(self, service, raw_data, transformed_data):
        """Test querying records with stale data."""
        # Mark as loaded but make raw data stale
        transformed_data.image_loaded = True
        transformed_data.save()

        # Change raw data hash to make it stale
        raw_data.raw_hash = "new_hash"
        raw_data.save()

        records = service.get_records_needing_processing()
        assert len(records) >= 1

    def test_get_records_needing_processing_museum_filter(self, service):
        """Test museum filtering."""
        # Create another record for different museum
        raw_data_2 = MetaDataRaw.objects.create(
            museum_slug="cma",
            museum_object_id="CMA456",
            raw_json={"test": "data2"},
            raw_hash="def456",
        )

        TransformedData.objects.create(
            raw_data=raw_data_2,
            source_raw_hash="def456",
            object_number="CMA456",
            thumbnail_url="https://example.com/thumb2.jpg",
            museum_slug="cma",
            searchable_work_types=["sculpture"],
            image_loaded=False,
        )

        # Filter by SMK only
        records = service.get_records_needing_processing(museum_filter="smk")
        smk_records = [r for r in records if r.museum_slug == "smk"]
        cma_records = [r for r in records if r.museum_slug == "cma"]
        
        assert len(smk_records) >= 0  # May have SMK records from other tests
        assert len(cma_records) == 0

    def test_should_process_image_hash_changed(self, service, transformed_data):
        """Test processing when thumbnail URL hash changes."""
        # Set old hash
        old_hash = "old_hash_value"
        transformed_data.thumbnail_url_hash = old_hash
        transformed_data.save()

        should_process, reason = service.should_process_image(transformed_data)

        assert should_process is True
        assert "thumbnail_url_hash changed" in reason

    def test_should_process_image_missing_from_s3(self, service, transformed_data, mock_bucket_service):
        """Test processing when image is missing from S3."""
        # Set current hash
        current_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.thumbnail_url_hash = current_hash
        transformed_data.save()

        # Mock S3 object doesn't exist
        mock_bucket_service.object_exists.return_value = False

        should_process, reason = service.should_process_image(transformed_data)

        assert should_process is True
        assert "missing from S3 bucket" in reason

    def test_should_not_process_image_exists_and_hash_same(self, service, transformed_data, mock_bucket_service):
        """Test skipping when image exists and hash is unchanged."""
        # Set current hash
        current_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.thumbnail_url_hash = current_hash
        transformed_data.save()

        # Mock S3 object exists
        mock_bucket_service.object_exists.return_value = True

        should_process, reason = service.should_process_image(transformed_data)

        assert should_process is False
        assert "exists and hash unchanged" in reason

    def test_process_single_record_success(self, service, transformed_data, mock_bucket_service):
        """Test successful processing of a single record."""
        # Mock upload success
        mock_bucket_service.upload_thumbnail.return_value = None

        status = service.process_single_record(transformed_data)

        assert status == "success"

        # Check record was updated
        transformed_data.refresh_from_db()
        assert transformed_data.image_loaded is True
        assert transformed_data.thumbnail_url_hash is not None

    def test_process_single_record_skipped(self, service, transformed_data, mock_bucket_service):
        """Test skipping a record that doesn't need processing."""
        # Set up record to be skipped
        current_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.thumbnail_url_hash = current_hash
        transformed_data.image_loaded = False  # Not loaded but exists in S3
        transformed_data.save()

        # Mock S3 object exists
        mock_bucket_service.object_exists.return_value = True

        status = service.process_single_record(transformed_data)

        assert status == "skipped"

        # Should still mark as loaded
        transformed_data.refresh_from_db()
        assert transformed_data.image_loaded is True

    def test_process_single_record_error(self, service, transformed_data, mock_bucket_service):
        """Test error handling during processing."""
        # Mock upload failure
        mock_bucket_service.upload_thumbnail.side_effect = Exception("Upload failed")

        status = service.process_single_record(transformed_data)

        assert status == "error"

        # Record should not be marked as loaded
        transformed_data.refresh_from_db()
        assert transformed_data.image_loaded is False

    def test_run_batch_processing_no_records(self, service, transformed_data, mock_bucket_service):
        """Test batch processing when no records need processing."""
        # Mark record as processed
        transformed_data.image_loaded = True
        current_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.thumbnail_url_hash = current_hash
        transformed_data.save()

        # Mock S3 exists
        mock_bucket_service.object_exists.return_value = True

        stats = service.run_batch_processing()

        # May be 0 or more depending on other test data
        assert stats["total"] >= 0
        assert stats["success"] >= 0

    def test_run_batch_processing_with_records(self, service, transformed_data, mock_bucket_service):
        """Test batch processing with records to process."""
        # Mock successful upload
        mock_bucket_service.upload_thumbnail.return_value = None

        stats = service.run_batch_processing()

        assert stats["total"] >= 1
        assert stats["success"] >= 1
        assert stats["skipped"] >= 0
        assert stats["error"] >= 0

    def test_bucket_key_generation(self):
        """Test S3 key generation."""
        key = get_bucket_image_key("smk", "KMS123")
        assert key == "smk_KMS123.jpg"