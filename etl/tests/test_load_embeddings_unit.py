from unittest.mock import Mock, patch
import pytest
from qdrant_client.http.models import PointStruct

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.load.load_embeddings.service import EmbeddingLoadService


@pytest.mark.unit
class TestEmbeddingLoadServiceUnit:
    @pytest.fixture
    def mock_clip_embedder(self):
        """Create mock CLIP embedder."""
        return Mock()

    @pytest.fixture
    def mock_qdrant_service(self):
        """Create mock Qdrant service."""
        mock_service = Mock()
        mock_service.qdrant_client.collection_exists.return_value = True
        return mock_service

    @pytest.fixture
    def service(self, mock_qdrant_service):
        """Create embedding load service with mocked dependencies."""
        with (
            patch(
                "etl.pipeline.load.load_embeddings.service.get_qdrant_service",
                return_value=mock_qdrant_service,
            ),
            patch(
                "etl.pipeline.load.load_embeddings.service.get_clip_embedder"
            ) as mock_get_embedder,
        ):
            mock_embedder = Mock()
            mock_get_embedder.return_value = mock_embedder

            service = EmbeddingLoadService(collection_name="test_collection")
            service.clip_embedder = mock_embedder
            return service

    @pytest.fixture
    def sample_transformed_data(self):
        """Create sample TransformedData for testing (not saved to DB)."""
        raw_data = MetaDataRaw(
            museum_slug="smk",
            museum_object_id="KMS123",
            raw_json={"test": "data"},
            raw_hash="abc123",
        )

        return TransformedData(
            pk=1,  # Set pk manually for testing
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

    def test_should_process_embedding_never_processed(
        self, service, sample_transformed_data
    ):
        """Test processing when embedding has never been processed."""
        sample_transformed_data.image_vector_clip = False

        should_process, reason = service.should_process_embedding(
            sample_transformed_data
        )

        assert should_process is True
        assert "never processed" in reason


    def test_should_not_process_embedding_up_to_date(
        self, service, sample_transformed_data
    ):
        """Test skipping when embedding is up to date."""
        import hashlib

        sample_transformed_data.image_vector_clip = True
        sample_transformed_data.source_raw_hash = "abc123"
        sample_transformed_data.raw_data.raw_hash = "abc123"
        # Set matching thumbnail hash
        sample_transformed_data.thumbnail_url_hash = hashlib.sha256(
            sample_transformed_data.thumbnail_url.encode()
        ).hexdigest()

        should_process, reason = service.should_process_embedding(
            sample_transformed_data
        )

        assert should_process is False
        assert "already processed and up-to-date" in reason

    def test_should_process_embedding_thumbnail_changed(
        self, service, sample_transformed_data
    ):
        """Test processing when thumbnail URL hash changes."""
        sample_transformed_data.image_vector_clip = True
        sample_transformed_data.source_raw_hash = "abc123"
        sample_transformed_data.raw_data.raw_hash = "abc123"
        # Set different thumbnail hash to simulate URL change
        sample_transformed_data.thumbnail_url_hash = "old_thumbnail_hash"

        should_process, reason = service.should_process_embedding(
            sample_transformed_data
        )

        assert should_process is True
        assert "thumbnail_changed" in reason

    def test_create_qdrant_point_structure(self, service, sample_transformed_data):
        """Test Qdrant point creation with correct structure."""
        test_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions

        point = service._create_qdrant_point(sample_transformed_data, test_embedding)

        assert isinstance(point, PointStruct)
        assert point.id == 1

        # Check vectors structure
        assert isinstance(point.vector, dict)
        assert "text_clip" in point.vector
        assert "image_clip" in point.vector
        assert "text_jina" in point.vector
        assert "image_jina" in point.vector

        # Check vector dimensions
        assert len(list(point.vector["text_clip"])) == 768
        assert len(list(point.vector["image_clip"])) == 768
        assert len(list(point.vector["text_jina"])) == 256
        assert len(list(point.vector["image_jina"])) == 256

        # Check that only image_clip has actual embedding
        assert point.vector["image_clip"] == test_embedding
        assert all(v == 0.0 for v in point.vector["text_clip"])
        assert all(v == 0.0 for v in point.vector["text_jina"])
        assert all(v == 0.0 for v in point.vector["image_jina"])

        # Check payload
        assert point.payload is not None
        assert point.payload["museum"] == "smk"
        assert point.payload["object_number"] == "KMS123"
        assert point.payload["title"] == "Test Artwork"
        assert point.payload["artist"] == "Test Artist"

    def test_process_single_record_success(self, service, sample_transformed_data):
        """Test successful processing of a single record."""
        test_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions

        # Mock embedding generation
        service.clip_embedder.generate_thumbnail_embedding.return_value = test_embedding

        # Mock the save method
        sample_transformed_data.save = Mock()

        with patch("django.db.transaction.atomic"):
            status = service.process_single_record(sample_transformed_data)

        assert status == "success"

        # Check that embedding was generated
        service.clip_embedder.generate_thumbnail_embedding.assert_called_once_with(
            thumbnail_url="https://example.com/thumb.jpg", object_number="KMS123"
        )

        # Check that point was uploaded
        service.qdrant_service.upload_points.assert_called_once()

        # Check that record was updated
        assert sample_transformed_data.image_vector_clip is True
        assert sample_transformed_data.thumbnail_url_hash is not None
        sample_transformed_data.save.assert_called_once_with(
            update_fields=["image_vector_clip", "thumbnail_url_hash"]
        )

    def test_process_single_record_embedding_failure(
        self, service, sample_transformed_data
    ):
        """Test handling embedding generation failure."""
        # Mock embedding generation failure
        service.clip_embedder.generate_thumbnail_embedding.return_value = None

        status = service.process_single_record(sample_transformed_data)

        assert status == "error"

        # Check that no upload was attempted
        service.qdrant_service.upload_points.assert_not_called()

    def test_process_single_record_skip_already_processed(
        self, service, sample_transformed_data
    ):
        """Test skipping already processed records."""
        import hashlib

        sample_transformed_data.image_vector_clip = True
        sample_transformed_data.source_raw_hash = "abc123"
        sample_transformed_data.raw_data.raw_hash = "abc123"
        # Set matching thumbnail hash to avoid processing
        sample_transformed_data.thumbnail_url_hash = hashlib.sha256(
            sample_transformed_data.thumbnail_url.encode()
        ).hexdigest()

        status = service.process_single_record(sample_transformed_data)

        assert status == "skipped"

        # Check that no embedding was generated
        service.clip_embedder.generate_thumbnail_embedding.assert_not_called()

        # Check that no upload was attempted
        service.qdrant_service.upload_points.assert_not_called()

    def test_process_single_record_exception_handling(
        self, service, sample_transformed_data
    ):
        """Test exception handling during processing."""
        # Mock embedding generation to raise an exception
        service.clip_embedder.generate_thumbnail_embedding.side_effect = Exception(
            "Test error"
        )

        status = service.process_single_record(sample_transformed_data)

        assert status == "error"

    def test_run_batch_processing_stats(self, service):
        """Test batch processing returns correct statistics."""
        # Mock get_records_needing_processing to return empty list
        with patch.object(service, "get_records_needing_processing", return_value=[]):
            stats = service.run_batch_processing()

        assert stats == {"success": 0, "skipped": 0, "error": 0, "total": 0}

    def test_get_records_needing_processing_force_flag(self, service):
        """Test force flag processes all records."""
        with patch(
            "etl.pipeline.load.load_embeddings.service.TransformedData.objects"
        ) as mock_objects:
            mock_query = Mock()
            mock_objects.filter.return_value.select_related.return_value.__getitem__ = (
                lambda self, key: mock_query
            )

            # Test force=False (normal behavior)
            service.get_records_needing_processing(force=False)

            # Should filter with specific conditions
            filter_call = mock_objects.filter.call_args[0][0]
            assert hasattr(filter_call, "children")  # Q object has children

            # Test force=True
            mock_objects.reset_mock()
            service.get_records_needing_processing(force=True)

            # Should filter with empty Q() (all records)
            filter_call = mock_objects.filter.call_args[0][0]
            assert (
                not hasattr(filter_call, "children") or len(filter_call.children) == 0
            )

    def test_collection_creation_on_init(self, mock_qdrant_service):
        """Test collection creation when it doesn't exist."""
        # Mock collection doesn't exist
        mock_qdrant_service.qdrant_client.collection_exists.return_value = False

        with (
            patch(
                "etl.pipeline.load.load_embeddings.service.get_qdrant_service",
                return_value=mock_qdrant_service,
            ),
            patch("etl.pipeline.load.load_embeddings.service.get_clip_embedder"),
        ):
            EmbeddingLoadService(collection_name="new_collection")

            # Check collection was created with correct config
            mock_qdrant_service.qdrant_client.create_collection.assert_called_once()
            call_args = mock_qdrant_service.qdrant_client.create_collection.call_args

            assert call_args[1]["collection_name"] == "new_collection"
            assert "vectors_config" in call_args[1]

            vectors_config = call_args[1]["vectors_config"]
            assert "text_clip" in vectors_config
            assert "image_clip" in vectors_config
            assert "text_jina" in vectors_config
            assert "image_jina" in vectors_config
