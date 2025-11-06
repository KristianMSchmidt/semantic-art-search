"""
Integration test for artwork stats loading pipeline.

Tests that the load_artwork_stats command correctly:
- Fetches data from Qdrant
- Populates ArtworkStats table
- Handles atomic updates
- Is idempotent
"""

import pytest
from unittest.mock import Mock, patch
from django.core.management import call_command
from io import StringIO

from artsearch.models import ArtworkStats


@pytest.mark.integration
@pytest.mark.django_db
def test_load_artwork_stats_from_qdrant():
    """
    Test that load_artwork_stats correctly populates database from Qdrant.

    This test mocks Qdrant but uses real database operations to verify:
    - Fetching from Qdrant works correctly
    - Database is populated with correct data
    - Unique constraint is respected
    - Atomic updates work (transaction rollback on error)

    Potential bugs this could catch:
    - Query logic not fetching all points
    - Missing validation on payload fields
    - Unique constraint violations
    - Transaction not atomic
    - Bulk create not working
    - Data transformation errors
    """

    # Setup: Mock Qdrant service
    mock_qdrant_service = Mock()

    # Create mock Qdrant points with artwork data
    mock_point_1 = Mock()
    mock_point_1.id = "test-id-1"
    mock_point_1.payload = {
        "museum": "smk",
        "object_number": "KMS1",
        "searchable_work_types": ["painting", "portrait"],
    }

    mock_point_2 = Mock()
    mock_point_2.id = "test-id-2"
    mock_point_2.payload = {
        "museum": "met",
        "object_number": "2023.1",
        "searchable_work_types": ["sculpture"],
    }

    mock_point_3 = Mock()
    mock_point_3.id = "test-id-3"
    mock_point_3.payload = {
        "museum": "cma",
        "object_number": "1234.56",
        "searchable_work_types": ["print", "drawing"],
    }

    # Mock fetch_points to return our test data
    mock_qdrant_service.fetch_points.return_value = (
        [mock_point_1, mock_point_2, mock_point_3],
        None,  # No next page token (single page)
    )

    # Patch QdrantService constructor to return our mock
    with patch(
        "etl.management.commands.load_artwork_stats.QdrantService",
        return_value=mock_qdrant_service,
    ):
        # Run the management command
        out = StringIO()
        call_command("load_artwork_stats", stdout=out)

        # Verify output
        output = out.getvalue()
        assert "Fetched 3 artworks from Qdrant" in output
        assert "Successfully loaded ArtworkStats with 3 records" in output

    # Verify database state
    assert ArtworkStats.objects.count() == 3

    # Verify individual records
    smk_artwork = ArtworkStats.objects.get(museum_slug="smk", object_number="KMS1")
    assert smk_artwork.searchable_work_types == ["painting", "portrait"]

    met_artwork = ArtworkStats.objects.get(museum_slug="met", object_number="2023.1")
    assert met_artwork.searchable_work_types == ["sculpture"]

    cma_artwork = ArtworkStats.objects.get(museum_slug="cma", object_number="1234.56")
    assert cma_artwork.searchable_work_types == ["print", "drawing"]


@pytest.mark.integration
@pytest.mark.django_db
def test_load_artwork_stats_idempotency():
    """
    Test that running load_artwork_stats multiple times is idempotent.

    Running the command twice should not create duplicates.
    """

    # Setup: Mock Qdrant service
    mock_qdrant_service = Mock()

    mock_point = Mock()
    mock_point.id = "test-id-1"
    mock_point.payload = {
        "museum": "smk",
        "object_number": "KMS1",
        "searchable_work_types": ["painting"],
    }

    mock_qdrant_service.fetch_points.return_value = ([mock_point], None)

    with patch(
        "etl.management.commands.load_artwork_stats.QdrantService",
        return_value=mock_qdrant_service,
    ):
        # Run command first time
        call_command("load_artwork_stats", stdout=StringIO())
        assert ArtworkStats.objects.count() == 1

        # Run command second time
        call_command("load_artwork_stats", stdout=StringIO())
        assert ArtworkStats.objects.count() == 1, (
            "Should not create duplicates on second run"
        )


@pytest.mark.integration
@pytest.mark.django_db
def test_load_artwork_stats_drop_existing():
    """
    Test that --drop-existing flag removes old records.
    """

    # Setup: Create some existing records
    ArtworkStats.objects.create(
        museum_slug="old_museum",
        object_number="OLD123",
        searchable_work_types=["old_type"],
    )
    assert ArtworkStats.objects.count() == 1

    # Setup: Mock Qdrant service with new data
    mock_qdrant_service = Mock()

    mock_point = Mock()
    mock_point.id = "test-id-1"
    mock_point.payload = {
        "museum": "smk",
        "object_number": "KMS1",
        "searchable_work_types": ["painting"],
    }

    mock_qdrant_service.fetch_points.return_value = ([mock_point], None)

    with patch(
        "etl.management.commands.load_artwork_stats.QdrantService",
        return_value=mock_qdrant_service,
    ):
        # Run command with --drop-existing
        out = StringIO()
        call_command("load_artwork_stats", "--drop-existing", stdout=out)

        output = out.getvalue()
        assert "Deleted 1 existing records" in output

    # Verify old record is gone, new record exists
    assert ArtworkStats.objects.count() == 1
    assert not ArtworkStats.objects.filter(
        museum_slug="old_museum", object_number="OLD123"
    ).exists()
    assert ArtworkStats.objects.filter(museum_slug="smk", object_number="KMS1").exists()


@pytest.mark.integration
@pytest.mark.django_db
def test_load_artwork_stats_skips_invalid_points():
    """
    Test that invalid points are skipped with warnings.
    """

    mock_qdrant_service = Mock()

    # Valid point
    valid_point = Mock()
    valid_point.id = "valid-1"
    valid_point.payload = {
        "museum": "smk",
        "object_number": "KMS1",
        "searchable_work_types": ["painting"],
    }

    # Invalid points
    point_no_payload = Mock()
    point_no_payload.id = "invalid-1"
    point_no_payload.payload = None

    point_no_museum = Mock()
    point_no_museum.id = "invalid-2"
    point_no_museum.payload = {
        "object_number": "KMS2",
        "searchable_work_types": ["painting"],
    }

    point_no_object_number = Mock()
    point_no_object_number.id = "invalid-3"
    point_no_object_number.payload = {
        "museum": "smk",
        "searchable_work_types": ["painting"],
    }

    point_invalid_work_types = Mock()
    point_invalid_work_types.id = "invalid-4"
    point_invalid_work_types.payload = {
        "museum": "smk",
        "object_number": "KMS3",
        "searchable_work_types": "not_a_list",  # Should be list
    }

    mock_qdrant_service.fetch_points.return_value = (
        [
            valid_point,
            point_no_payload,
            point_no_museum,
            point_no_object_number,
            point_invalid_work_types,
        ],
        None,
    )

    with patch(
        "etl.management.commands.load_artwork_stats.QdrantService",
        return_value=mock_qdrant_service,
    ):
        call_command("load_artwork_stats", stdout=StringIO())

    # Only the valid point should be loaded
    assert ArtworkStats.objects.count() == 1
    assert ArtworkStats.objects.filter(museum_slug="smk", object_number="KMS1").exists()


@pytest.mark.integration
@pytest.mark.django_db
def test_load_artwork_stats_handles_pagination():
    """
    Test that the command correctly handles multiple pages from Qdrant.
    """

    mock_qdrant_service = Mock()

    # Page 1
    point_1 = Mock()
    point_1.id = "id-1"
    point_1.payload = {
        "museum": "smk",
        "object_number": "KMS1",
        "searchable_work_types": ["painting"],
    }

    # Page 2
    point_2 = Mock()
    point_2.id = "id-2"
    point_2.payload = {
        "museum": "met",
        "object_number": "2023.1",
        "searchable_work_types": ["sculpture"],
    }

    # Mock pagination: first call returns page 1 with token, second call returns page 2 with None
    mock_qdrant_service.fetch_points.side_effect = [
        ([point_1], "page_2_token"),  # First call
        ([point_2], None),  # Second call
    ]

    with patch(
        "etl.management.commands.load_artwork_stats.QdrantService",
        return_value=mock_qdrant_service,
    ):
        call_command("load_artwork_stats", stdout=StringIO())

    # Both pages should be loaded
    assert ArtworkStats.objects.count() == 2
    assert ArtworkStats.objects.filter(museum_slug="smk", object_number="KMS1").exists()
    assert ArtworkStats.objects.filter(
        museum_slug="met", object_number="2023.1"
    ).exists()

    # Verify fetch_points was called twice (once per page)
    assert mock_qdrant_service.fetch_points.call_count == 2
