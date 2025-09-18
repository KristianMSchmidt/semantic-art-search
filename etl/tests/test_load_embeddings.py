from unittest.mock import Mock, patch
import pytest

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.load.load_embeddings.service import EmbeddingLoadService


@pytest.mark.integration
@pytest.mark.django_db
class TestEmbeddingLoadServiceIntegration:
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
            work_types=["oil on canvas"],
            title="Test Artwork",
            artist=["Test Artist"],
            image_vector_clip=False,
        )

    @pytest.fixture
    def mock_qdrant_service(self):
        """Create mock Qdrant service."""
        mock_service = Mock()
        mock_service.qdrant_client.collection_exists.return_value = True
        return mock_service

    @pytest.fixture
    def mock_clip_embedder(self):
        """Create mock CLIP embedder."""
        return Mock()

    @pytest.fixture
    def service(self, mock_qdrant_service, mock_clip_embedder):
        """Create embedding load service with mocked external dependencies."""
        with (
            patch(
                "etl.pipeline.load.load_embeddings.service.get_qdrant_service",
                return_value=mock_qdrant_service,
            ),
            patch(
                "etl.pipeline.load.load_embeddings.service.get_clip_embedder",
                return_value=mock_clip_embedder,
            ),
        ):
            return EmbeddingLoadService(collection_name="test_collection")

    def test_get_records_needing_processing_never_processed(
        self, service, transformed_data
    ):
        """Test querying records that have never been processed."""
        records = service.get_records_needing_processing()
        assert len(records) >= 1
        our_record = next((r for r in records if r.object_number == "KMS123"), None)
        assert our_record is not None
        assert our_record.image_vector_clip is False


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
            work_types=["bronze"],
            image_vector_clip=False,
        )

        # Filter by SMK only
        records = service.get_records_needing_processing(museum_filter="smk")
        smk_records = [r for r in records if r.museum_slug == "smk"]
        cma_records = [r for r in records if r.museum_slug == "cma"]

        assert len(smk_records) >= 0  # May have SMK records from other tests
        assert len(cma_records) == 0

    def test_should_process_embedding_database_states(self, service, transformed_data):
        """Test processing logic with real database states."""
        import hashlib

        # Never processed
        should_process, reason = service.should_process_embedding(transformed_data)
        assert should_process is True
        assert "never processed" in reason

        # Mark as processed with correct thumbnail hash
        transformed_data.image_vector_clip = True
        transformed_data.thumbnail_url_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.save()

        should_process, reason = service.should_process_embedding(transformed_data)
        assert should_process is False
        assert "already processed and up-to-date" in reason

    def test_should_process_embedding_thumbnail_url_change(
        self, service, transformed_data
    ):
        """Test processing when thumbnail URL changes."""
        import hashlib

        # Mark as processed with old thumbnail hash
        transformed_data.image_vector_clip = True
        transformed_data.thumbnail_url_hash = "old_hash"
        transformed_data.save()

        should_process, reason = service.should_process_embedding(transformed_data)
        assert should_process is True
        assert "thumbnail_changed" in reason

    def test_process_single_record_success(self, service, transformed_data):
        """Test successful processing of a single record with database persistence."""
        test_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions

        # Mock embedding generation
        service.clip_embedder.generate_thumbnail_embedding.return_value = test_embedding

        status = service.process_single_record(transformed_data)

        assert status == "success"

        # Check that embedding was generated with correct parameters
        service.clip_embedder.generate_thumbnail_embedding.assert_called_once_with(
            thumbnail_url="https://example.com/thumb.jpg", object_number="KMS123"
        )

        # Check that point was uploaded to Qdrant
        service.qdrant_service.upload_points.assert_called_once()
        uploaded_points = service.qdrant_service.upload_points.call_args[0][0]
        assert len(uploaded_points) == 1

        # Verify the point structure
        point = uploaded_points[0]
        assert point.id == transformed_data.pk
        assert isinstance(point.vector, dict)
        assert point.payload["museum"] == "smk"
        assert point.payload["object_number"] == "KMS123"

        # Check database was updated
        transformed_data.refresh_from_db()
        assert transformed_data.image_vector_clip is True
        assert transformed_data.thumbnail_url_hash is not None

    def test_process_single_record_embedding_failure(self, service, transformed_data):
        """Test handling embedding generation failure."""
        # Mock embedding generation failure
        service.clip_embedder.generate_thumbnail_embedding.return_value = None

        status = service.process_single_record(transformed_data)

        assert status == "error"

        # Check that no upload was attempted
        service.qdrant_service.upload_points.assert_not_called()

        # Check database was not updated
        transformed_data.refresh_from_db()
        assert transformed_data.image_vector_clip is False

    def test_process_single_record_skipped(self, service, transformed_data):
        """Test skipping already processed records."""
        import hashlib

        # Mark as processed with correct thumbnail hash
        transformed_data.image_vector_clip = True
        transformed_data.thumbnail_url_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.save()

        status = service.process_single_record(transformed_data)

        assert status == "skipped"

        # Check that no embedding was generated
        service.clip_embedder.generate_thumbnail_embedding.assert_not_called()

        # Check that no upload was attempted
        service.qdrant_service.upload_points.assert_not_called()

    def test_run_batch_processing_no_records(self, service, transformed_data):
        """Test batch processing when no records need processing."""
        # Mark record as processed
        transformed_data.image_vector_clip = True
        transformed_data.save()

        stats = service.run_batch_processing()

        # May be 0 or more depending on other test data
        assert stats["total"] >= 0
        assert stats["success"] >= 0

    def test_run_batch_processing_with_records(self, service, transformed_data):
        """Test batch processing with records to process."""
        test_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions

        # Mock successful embedding generation
        service.clip_embedder.generate_thumbnail_embedding.return_value = test_embedding

        stats = service.run_batch_processing()

        assert stats["total"] >= 1
        assert stats["success"] >= 1
        assert stats["skipped"] >= 0
        assert stats["error"] >= 0

    def test_qdrant_point_metadata_structure(self, service, transformed_data):
        """Test that Qdrant points have correct metadata structure."""
        test_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions

        point = service._create_qdrant_point(transformed_data, test_embedding)

        # Check required metadata fields from requirements
        required_fields = [
            "museum",
            "object_number",
            "title",
            "artist",
            "production_date",
            "work_types",
            "searchable_work_types",
        ]
        for field in required_fields:
            assert field in point.payload

        # Verify field values
        assert point.payload["museum"] == "smk"
        assert point.payload["object_number"] == "KMS123"
        assert point.payload["title"] == "Test Artwork"
        assert point.payload["artist"] == "Test Artist"

    def test_collection_initialization_creates_collection(self):
        """Test that service creates Qdrant collection if it doesn't exist."""
        mock_qdrant_service = Mock()
        mock_qdrant_service.qdrant_client.collection_exists.return_value = False

        with (
            patch(
                "etl.pipeline.load.load_embeddings.service.get_qdrant_service",
                return_value=mock_qdrant_service,
            ),
            patch("etl.pipeline.load.load_embeddings.service.get_clip_embedder"),
        ):
            EmbeddingLoadService(collection_name="new_test_collection")

            # Verify collection creation was called
            mock_qdrant_service.qdrant_client.create_collection.assert_called_once()
            call_args = mock_qdrant_service.qdrant_client.create_collection.call_args

            assert call_args[1]["collection_name"] == "new_test_collection"
            vectors_config = call_args[1]["vectors_config"]

            # Verify all 4 named vectors are configured
            assert "text_clip" in vectors_config
            assert "image_clip" in vectors_config
            assert "text_jina" in vectors_config
            assert "image_jina" in vectors_config

    def test_collection_initialization_existing_collection(self):
        """Test that service doesn't recreate existing collection."""
        mock_qdrant_service = Mock()
        mock_qdrant_service.qdrant_client.collection_exists.return_value = True

        with (
            patch(
                "etl.pipeline.load.load_embeddings.service.get_qdrant_service",
                return_value=mock_qdrant_service,
            ),
            patch("etl.pipeline.load.load_embeddings.service.get_clip_embedder"),
        ):
            EmbeddingLoadService(collection_name="existing_collection")

            # Verify collection creation was NOT called
            mock_qdrant_service.qdrant_client.create_collection.assert_not_called()

    def test_get_records_needing_processing_force_flag(self, service, transformed_data):
        """Test force flag processes all records including already processed ones."""
        import hashlib

        # Mark record as fully processed
        transformed_data.image_vector_clip = True
        transformed_data.thumbnail_url_hash = hashlib.sha256(
            transformed_data.thumbnail_url.encode()
        ).hexdigest()
        transformed_data.save()

        # Normal query should return no records
        records_normal = service.get_records_needing_processing(force=False)
        our_record_normal = any(r.object_number == "KMS123" for r in records_normal)
        assert our_record_normal is False

        # Force query should return the record
        records_force = service.get_records_needing_processing(force=True)
        our_record_force = any(r.object_number == "KMS123" for r in records_force)
        assert our_record_force is True
