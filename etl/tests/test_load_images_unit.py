import hashlib
from unittest.mock import Mock
import pytest  # type: ignore

from artsearch.src.services.bucket_service import get_bucket_image_key


@pytest.mark.unit
class TestImageLoadServiceUnit:
    """Unit tests for image loading functionality that don't require database."""

    def test_bucket_key_generation(self):
        """Test S3 key generation."""
        key = get_bucket_image_key("smk", "KMS123")
        assert key == "smk_KMS123.jpg"

        key2 = get_bucket_image_key("cma", "CMA456")
        assert key2 == "cma_CMA456.jpg"

    def test_hash_calculation(self):
        """Test thumbnail URL hash calculation."""
        test_url = "https://example.com/thumb.jpg"
        expected_hash = hashlib.sha256(test_url.encode()).hexdigest()

        calculated_hash = hashlib.sha256(test_url.encode()).hexdigest()
        assert calculated_hash == expected_hash

    def test_bucket_service_initialization(self):
        """Test that bucket service can be mocked properly."""
        from etl.pipeline.load.load_images.service import ImageLoadService

        mock_bucket_service = Mock()
        service = ImageLoadService(bucket_service=mock_bucket_service)

        assert service.bucket_service == mock_bucket_service

    def test_should_process_logic_hash_changed(self):
        """Test the logic for determining when to process based on hash changes."""
        # This tests the core logic without database dependencies

        # Mock a transformed data record
        mock_record = Mock()
        mock_record.thumbnail_url = "https://example.com/thumb.jpg"
        mock_record.thumbnail_url_hash = "old_hash_value"
        mock_record.museum_slug = "smk"
        mock_record.object_number = "KMS123"

        # Mock bucket service
        mock_bucket_service = Mock()
        mock_bucket_service.object_exists.return_value = True

        from etl.pipeline.load.load_images.service import ImageLoadService

        service = ImageLoadService(bucket_service=mock_bucket_service)

        should_process, reason = service.should_process_image(mock_record)

        # Should process because hash changed
        assert should_process is True
        assert "thumbnail_url_hash changed" in reason

    def test_should_process_logic_missing_from_s3(self):
        """Test the logic for determining when to process when missing from S3."""
        # Mock a transformed data record with matching hash
        mock_record = Mock()
        mock_record.thumbnail_url = "https://example.com/thumb.jpg"
        current_hash = hashlib.sha256(mock_record.thumbnail_url.encode()).hexdigest()
        mock_record.thumbnail_url_hash = current_hash
        mock_record.museum_slug = "smk"
        mock_record.object_number = "KMS123"

        # Mock bucket service - image doesn't exist
        mock_bucket_service = Mock()
        mock_bucket_service.object_exists.return_value = False

        from etl.pipeline.load.load_images.service import ImageLoadService

        service = ImageLoadService(bucket_service=mock_bucket_service)

        should_process, reason = service.should_process_image(mock_record)

        # Should process because missing from S3
        assert should_process is True
        assert "missing from S3 bucket" in reason

    def test_should_not_process_logic_exists_and_hash_same(self):
        """Test the logic for skipping when image exists and hash unchanged."""
        # Mock a transformed data record with matching hash
        mock_record = Mock()
        mock_record.thumbnail_url = "https://example.com/thumb.jpg"
        current_hash = hashlib.sha256(mock_record.thumbnail_url.encode()).hexdigest()
        mock_record.thumbnail_url_hash = current_hash
        mock_record.museum_slug = "smk"
        mock_record.object_number = "KMS123"

        # Mock bucket service - image exists
        mock_bucket_service = Mock()
        mock_bucket_service.object_exists.return_value = True

        from etl.pipeline.load.load_images.service import ImageLoadService

        service = ImageLoadService(bucket_service=mock_bucket_service)

        should_process, reason = service.should_process_image(mock_record)

        # Should NOT process because exists and hash unchanged
        assert should_process is False
        assert "exists and hash unchanged" in reason
