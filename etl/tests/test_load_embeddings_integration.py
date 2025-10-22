"""
Integration test for embedding load pipeline.

Tests WHAT the embedding pipeline should do (generate embeddings and track state),
not HOW it does it (implementation details).
"""

import pytest
import requests
from unittest.mock import Mock, MagicMock, patch

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

    # Setup mocks
    mock_clip_embedder = Mock()

    mock_qdrant_service = Mock()
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.collection_exists.return_value = True
    mock_qdrant_service.qdrant_client = mock_qdrant_client

    service = EmbeddingLoadService(
        collection_name="test_collection",
        clip_embedder=mock_clip_embedder,
        qdrant_service=mock_qdrant_service,
    )

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
    # Setup mocks
    mock_clip_embedder = Mock()
    # Return fake 768-dimensional embedding
    fake_embedding = [0.1] * 768
    mock_clip_embedder.generate_thumbnail_embedding.return_value = fake_embedding

    mock_qdrant_service = Mock()
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.collection_exists.return_value = True
    mock_qdrant_service.qdrant_client = mock_qdrant_client

    # Create service with dependency injection
    service = EmbeddingLoadService(
        collection_name="test_collection",
        clip_embedder=mock_clip_embedder,
        qdrant_service=mock_qdrant_service,
    )

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
        "Point ID should be UUID5 based on museum+object_number"
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


@pytest.mark.integration
@pytest.mark.django_db
def test_failed_embeddings_are_marked_and_skipped():
    """
    Test that permanent errors (invalid image, CLIP errors) fail immediately without retries.

    This test verifies the fix for the infinite loop bug where embedding generation
    errors would cause the same records to be retried indefinitely.

    Tests:
    - Permanent errors fail immediately (no retries)
    - Failed embeddings set embedding_load_failed=True
    - Failed records are excluded from get_records_needing_processing
    - reset_embedding_load_failed_field allows retrying failed embeddings
    """

    # Step 1: Create a test record with image_loaded=True
    transformed = TransformedData.objects.create(
        museum_slug="test",
        object_number="TEST_EMBED_001",
        museum_db_id="test-embed-id-001",
        thumbnail_url="https://example.com/test.jpg",
        searchable_work_types=["painting"],
        image_loaded=True,  # Prerequisite met
        image_load_failed=False,
        embedding_load_failed=False,
        image_vector_clip=False,
    )

    # Step 2: Process with mocked CLIP embedder that raises permanent error
    mock_clip_embedder = Mock()
    # Simulate corrupted image error (permanent error - should not retry)
    mock_clip_embedder.generate_thumbnail_embedding.side_effect = ValueError(
        "Cannot identify image file - corrupted or invalid format"
    )

    mock_qdrant_service = Mock()
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.collection_exists.return_value = True
    mock_qdrant_service.qdrant_client = mock_qdrant_client

    service = EmbeddingLoadService(
        collection_name="test_collection",
        clip_embedder=mock_clip_embedder,
        qdrant_service=mock_qdrant_service,
    )

    # Process - should fail immediately without retries
    status = service.process_single_record(transformed, delay_seconds=0.0)
    assert status == "error", "Processing should return error status"

    # Verify generate_thumbnail_embedding was called exactly once (no retries)
    assert mock_clip_embedder.generate_thumbnail_embedding.call_count == 1, (
        "Permanent errors should fail immediately without retries"
    )

    # Verify embedding_load_failed was set
    transformed.refresh_from_db()
    assert transformed.image_vector_clip is False, "image_vector_clip should still be False"
    assert transformed.embedding_load_failed is True, (
        "embedding_load_failed should be True after error"
    )

    # Step 3: Verify record is excluded from future queries
    records = service.get_records_needing_processing(
        batch_size=100, museum_filter="test"
    )
    our_records = [r for r in records if r.object_number == "TEST_EMBED_001"]

    assert len(our_records) == 0, (
        "Failed record should be excluded from get_records_needing_processing"
    )

    # Step 4: Test reset_embedding_load_failed_field
    count = service.reset_embedding_load_failed_field(museum_filter="test")
    assert count >= 1, "Should reset at least our test record"

    transformed.refresh_from_db()
    assert transformed.embedding_load_failed is False, (
        "reset_embedding_load_failed_field should set flag to False"
    )

    # Step 5: Verify record is included again after reset
    records = service.get_records_needing_processing(
        batch_size=100, museum_filter="test"
    )
    our_records = [r for r in records if r.object_number == "TEST_EMBED_001"]
    assert len(our_records) == 1, "After reset, failed record should be retryable"


@pytest.mark.integration
@pytest.mark.django_db
def test_transient_embedding_errors_are_retried():
    """
    Test that transient errors (Qdrant connection, network timeouts) are retried.

    Tests:
    - Transient errors trigger retries (up to max_retries)
    - Exponential backoff is used between retries
    - Success after retry marks image_vector_clip=True
    - Exhausted retries mark embedding_load_failed=True
    """

    # Test Case 1: Success on second retry
    transformed1 = TransformedData.objects.create(
        museum_slug="test",
        object_number="TEST_EMBED_002",
        museum_db_id="test-embed-id-002",
        thumbnail_url="https://example.com/test2.jpg",
        searchable_work_types=["painting"],
        image_loaded=True,
        image_load_failed=False,
        embedding_load_failed=False,
        image_vector_clip=False,
    )

    # Mock CLIP embedder to succeed after one transient error
    mock_clip_embedder = Mock()
    fake_embedding = [0.1] * 768

    # First call raises Qdrant connection error, second succeeds
    mock_clip_embedder.generate_thumbnail_embedding.side_effect = [
        RuntimeError("Qdrant connection timeout - please retry"),
        fake_embedding,  # Success on second attempt
    ]

    mock_qdrant_service = Mock()
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.collection_exists.return_value = True
    mock_qdrant_service.qdrant_client = mock_qdrant_client

    service = EmbeddingLoadService(
        collection_name="test_collection",
        clip_embedder=mock_clip_embedder,
        qdrant_service=mock_qdrant_service,
    )

    # Process - should succeed after retry
    with patch("time.sleep"):  # Mock sleep to speed up test
        status = service.process_single_record(transformed1, delay_seconds=0.0)

    assert status == "success", "Should succeed after retry"
    assert mock_clip_embedder.generate_thumbnail_embedding.call_count == 2, (
        "Should have retried once (2 total calls)"
    )

    # Verify success state
    transformed1.refresh_from_db()
    assert transformed1.image_vector_clip is True, "image_vector_clip should be True"
    assert transformed1.embedding_load_failed is False, (
        "embedding_load_failed should be False"
    )

    # Test Case 2: All retries exhausted
    transformed2 = TransformedData.objects.create(
        museum_slug="test",
        object_number="TEST_EMBED_003",
        museum_db_id="test-embed-id-003",
        thumbnail_url="https://example.com/test3.jpg",
        searchable_work_types=["painting"],
        image_loaded=True,
        image_load_failed=False,
        embedding_load_failed=False,
        image_vector_clip=False,
    )

    # Mock CLIP embedder to always fail with transient error
    mock_clip_embedder2 = Mock()
    mock_clip_embedder2.generate_thumbnail_embedding.side_effect = RuntimeError(
        "Qdrant connection timeout - please retry"
    )

    service2 = EmbeddingLoadService(
        collection_name="test_collection",
        clip_embedder=mock_clip_embedder2,
        qdrant_service=mock_qdrant_service,
    )

    # Process - should fail after all retries
    with patch("time.sleep"):  # Mock sleep to speed up test
        status = service2.process_single_record(
            transformed2, delay_seconds=0.0, max_retries=3
        )

    assert status == "error", "Should fail after exhausting retries"
    assert mock_clip_embedder2.generate_thumbnail_embedding.call_count == 3, (
        "Should have tried 3 times (max_retries=3)"
    )

    # Verify failed state
    transformed2.refresh_from_db()
    assert transformed2.image_vector_clip is False, "image_vector_clip should be False"
    assert transformed2.embedding_load_failed is True, (
        "embedding_load_failed should be True after exhausting retries"
    )
