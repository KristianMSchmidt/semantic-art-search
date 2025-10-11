"""
Integration test for embedding load pipeline.

Tests WHAT the embedding pipeline should do (generate embeddings and track state),
not HOW it does it (implementation details).
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.extract.extractors.smk_extractor import (
    BASE_SEARCH_URL,
    fetch_raw_data_from_smk_api,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.pipeline.transform.transform import transform_and_upsert
from etl.services.embedding_load_service import EmbeddingLoadService
from etl.utils import generate_uuid5


@pytest.mark.integration
@pytest.mark.django_db
def test_embedding_load_updates_vector_flags_and_respects_prerequisites():
    """
    Test that embedding loading correctly manages vector flags and prerequisites.

    This test uses real database operations but mocks CLIP model and Qdrant
    to avoid expensive GPU inference and external service dependencies.

    Tests:
    - Fetch real SMK artwork (extraction)
    - Transform to TransformedData (transformation)
    - Set image_loaded=True (prerequisite for embeddings)
    - Process embedding generation (load step)
    - Vector flags correctly updated
    - Idempotency: processing twice doesn't recalculate
    - Qdrant point structure is correct
    - Only processes records with image_loaded=True

    Potential bugs this could catch:
    - Query logic returning records without images loaded
    - Vector flags not being set (infinite reprocessing)
    - Idempotency broken (waste GPU/money)
    - Wrong vector dimensions for Qdrant
    - Malformed Qdrant points
    - Missing payload fields
    - Active vector system broken
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

    # Step 3: Verify initial state
    assert transformed.image_vector_clip is False, (
        "Should start with image_vector_clip=False"
    )
    assert transformed.text_vector_clip is False, (
        "Should start with text_vector_clip=False"
    )

    # Step 4: Test prerequisite - should NOT process if image_loaded=False
    assert transformed.image_loaded is False, "Should start with image_loaded=False"

    with (
        patch("etl.services.embedding_load_service.get_clip_embedder") as mock_get_clip,
        patch(
            "etl.services.embedding_load_service.get_qdrant_service"
        ) as mock_get_qdrant,
    ):
        # Setup mocks
        mock_clip_embedder = Mock()
        mock_get_clip.return_value = mock_clip_embedder

        mock_qdrant_service = Mock()
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.collection_exists.return_value = True
        mock_qdrant_service.qdrant_client = mock_qdrant_client
        mock_get_qdrant.return_value = mock_qdrant_service

        service = EmbeddingLoadService(collection_name="test_collection")

        # Should return empty because image_loaded=False
        records = service.get_records_needing_processing(
            batch_size=100, museum_filter="smk"
        )
        our_records = [r for r in records if r.object_number == object_number]
        assert len(our_records) == 0, "Should not process records without images loaded"

    # Step 5: Set image_loaded=True (simulating image load pipeline completion)
    transformed.image_loaded = True
    transformed.save(update_fields=["image_loaded"])

    # Step 6: Now test embedding processing with mocked CLIP and Qdrant
    with (
        patch("etl.services.embedding_load_service.get_clip_embedder") as mock_get_clip,
        patch(
            "etl.services.embedding_load_service.get_qdrant_service"
        ) as mock_get_qdrant,
    ):
        # Setup mocks
        mock_clip_embedder = Mock()
        # Return fake 768-dimensional embedding
        fake_embedding = [0.1] * 768
        mock_clip_embedder.generate_thumbnail_embedding.return_value = fake_embedding
        mock_get_clip.return_value = mock_clip_embedder

        mock_qdrant_service = Mock()
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.collection_exists.return_value = True
        mock_qdrant_service.qdrant_client = mock_qdrant_client
        mock_get_qdrant.return_value = mock_qdrant_service

        # Create service
        service = EmbeddingLoadService(collection_name="test_collection")

        # Should now return our record (image_loaded=True, vector missing)
        records = service.get_records_needing_processing(
            batch_size=100, museum_filter="smk"
        )
        our_records = [r for r in records if r.object_number == object_number]
        assert len(our_records) == 1, (
            "Should process records with images loaded and vector missing"
        )

        # Process the record
        transformed.refresh_from_db()
        status = service.process_single_record(transformed, delay_seconds=0.0)

        assert status == "success", "Processing should succeed"

        # Verify CLIP embedder was called
        mock_clip_embedder.generate_thumbnail_embedding.assert_called_once()

        # Verify Qdrant upload was called
        mock_qdrant_service.upload_points.assert_called_once()

        # Verify the Qdrant point structure
        upload_call_args = mock_qdrant_service.upload_points.call_args
        points = upload_call_args[0][0]
        assert len(points) == 1, "Should upload exactly 1 point"

        point = points[0]
        # Verify UUID5 is deterministic
        expected_id = generate_uuid5(transformed.museum_slug, transformed.object_number)
        assert point.id == expected_id, (
            f"Point ID should be UUID5 based on museum+object_number"
        )

        # Verify named vectors structure
        vectors = point.vector
        assert "image_clip" in vectors, "Should have image_clip vector"
        assert "text_clip" in vectors, "Should have text_clip vector (zero)"
        assert "image_jina" in vectors, "Should have image_jina vector (zero)"
        assert "text_jina" in vectors, "Should have text_jina vector (zero)"

        # Verify active vector has calculated values
        assert vectors["image_clip"] == fake_embedding, (
            "image_clip should have calculated values"
        )

        # Verify non-active vectors have zeros
        assert vectors["text_clip"] == [0.0] * 768, "text_clip should be zero vector"
        assert vectors["image_jina"] == [0.0] * 256, "image_jina should be zero vector"
        assert vectors["text_jina"] == [0.0] * 256, "text_jina should be zero vector"

        # Verify payload structure
        payload = point.payload
        assert payload["museum"] == "smk", "Payload should have museum"
        assert payload["object_number"] == object_number, (
            "Payload should have object_number"
        )
        assert "museum_db_id" in payload, "Payload should have museum_db_id"
        assert payload["museum_db_id"] == museum_db_id, (
            "Payload museum_db_id should match record"
        )
        assert "title" in payload, "Payload should have title"
        assert "artist" in payload, "Payload should have artist"
        assert "production_date" in payload, "Payload should have production_date"
        assert "work_types" in payload, "Payload should have work_types"
        assert "searchable_work_types" in payload, (
            "Payload should have searchable_work_types"
        )

        # Verify database flag was updated
        transformed.refresh_from_db()
        assert transformed.image_vector_clip is True, (
            "image_vector_clip should be True after processing"
        )
        assert transformed.text_vector_clip is False, (
            "text_vector_clip should still be False (not active)"
        )

        # Step 7: Test idempotency - process again
        mock_clip_embedder.reset_mock()
        mock_qdrant_service.reset_mock()

        # Get records needing processing - should be empty now
        records = service.get_records_needing_processing(
            batch_size=100, museum_filter="smk"
        )
        our_records = [r for r in records if r.object_number == object_number]

        assert len(our_records) == 0, (
            "Record with all active vectors calculated should not be returned"
        )

        # Process again - should skip
        transformed.refresh_from_db()
        status = service.process_single_record(transformed, delay_seconds=0.0)

        assert status == "success", "Processing should succeed (but skip)"

        # Verify CLIP and Qdrant were NOT called (skipped because already calculated)
        mock_clip_embedder.generate_thumbnail_embedding.assert_not_called()
        mock_qdrant_service.upload_points.assert_not_called()

    # Step 8: Test reset functionality
    count = service.reset_vector_fields(museum_filter="smk")
    assert count >= 1, "Should reset at least our test record"

    transformed.refresh_from_db()
    assert transformed.image_vector_clip is False, (
        "reset_vector_fields should set flag to False"
    )

    # Now should need processing again
    records = service.get_records_needing_processing(
        batch_size=100, museum_filter="smk"
    )
    our_records = [r for r in records if r.object_number == object_number]
    assert len(our_records) == 1, "After reset, record should need processing again"
