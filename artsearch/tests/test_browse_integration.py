"""
Integration tests for browse mode (random artwork browsing with pagination).

Tests the full flow: view → search_service → browse_service → Qdrant

Following CLAUDE.md test principles:
- What-focused: Test business outcomes
- Integration over unit: Test entire request/response flow
- Mock expensive dependencies: Mock Qdrant, PostgreSQL queries
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from django.urls import reverse

from artsearch.src.services.search_service import handle_search


@pytest.fixture
def mock_qdrant_service():
    """Mock Qdrant service for all tests."""
    mock_service = MagicMock()
    mock_service.get_items_by_ids.return_value = []
    mock_service.search_text.return_value = ([], "jina")
    mock_service.search_similar_images.return_value = []
    mock_service.get_items_by_object_number.return_value = []

    with patch(
        "artsearch.src.services.search_service.QdrantService",
        return_value=mock_service,
    ), patch(
        "artsearch.src.services.browse_service.QdrantService",
        return_value=mock_service,
    ):
        yield mock_service


@pytest.fixture
def mock_random_artwork_ids():
    """Mock get_random_artwork_ids to control PostgreSQL behavior."""
    with patch(
        "artsearch.src.services.browse_service.get_random_artwork_ids"
    ) as mock:
        yield mock


@pytest.mark.integration
@pytest.mark.django_db
def test_browse_mode_returns_no_header_on_initial_load(
    mock_qdrant_service, mock_random_artwork_ids
):
    """
    Test that initial page load (no query param) shows no header text.

    This test verifies:
    - Initial load (query=None) returns empty header text
    - Browse mode is triggered when query parameter is absent

    Potential bugs this could catch:
    - Browse mode not triggered on initial load
    - Unwanted header text appearing on initial load
    """
    mock_random_artwork_ids.return_value = []

    client = Client()
    url = reverse("get-artworks")

    response = client.get(url)

    assert response.status_code == 200
    assert response.context["header_text"] == ""


@pytest.mark.integration
@pytest.mark.django_db
def test_empty_query_returns_search_results_header(
    mock_qdrant_service, mock_random_artwork_ids
):
    """
    Test that explicit empty query (`?query=`) shows result count header.

    This test verifies:
    - Empty string query shows "Search results (N)" format
    - Distinguishes between initial load (query=None) and explicit empty search

    Potential bugs this could catch:
    - Empty query treated same as missing query
    - Result count not displayed for empty searches
    """
    mock_random_artwork_ids.return_value = []

    client = Client()
    url = reverse("get-artworks") + "?query="

    with patch(
        "artsearch.views.context_builders.get_total_works_for_filters",
        return_value=42,
    ):
        response = client.get(url)

    assert response.status_code == 200
    assert response.context["header_text"] == "Search results (42)"


@pytest.mark.integration
@pytest.mark.django_db
def test_seed_included_in_pagination_urls_for_browse_mode(
    mock_qdrant_service, mock_random_artwork_ids
):
    """
    Test that next page URL contains seed parameter for browse mode.

    This test verifies:
    - Seed is preserved in pagination URLs when browsing
    - Ensures consistent ordering across infinite scroll pages

    Potential bugs this could catch:
    - Seed lost on pagination, causing random reordering
    - Pagination URLs missing required parameters
    """
    mock_random_artwork_ids.return_value = [("smk", "KMS1")]
    mock_qdrant_service.get_items_by_ids.return_value = [
        MagicMock(payload={"museum": "smk", "object_number": "KMS1"})
    ]

    client = Client()
    url = reverse("get-artworks") + "?seed=test123"

    response = client.get(url)

    assert response.status_code == 200
    urls = response.context["urls"]
    assert "seed=test123" in urls["get_artworks_with_params"]


@pytest.mark.integration
@pytest.mark.django_db
def test_seed_not_included_in_pagination_urls_for_search_mode(
    mock_qdrant_service,
):
    """
    Test that search with query doesn't include seed in pagination URLs.

    This test verifies:
    - Seeds are only for browse mode, not vector search
    - Search mode uses vector similarity ordering, not random

    Potential bugs this could catch:
    - Seed incorrectly added to search pagination
    - Browse-specific params leaking into search mode
    """
    mock_qdrant_service.search_text.return_value = (
        [MagicMock(payload={"museum": "smk", "object_number": "KMS1"})],
        "jina",
    )

    client = Client()
    url = reverse("get-artworks") + "?query=landscape&seed=test123"

    with patch(
        "artsearch.views.context_builders.get_total_works_for_filters",
        return_value=10,
    ):
        response = client.get(url)

    assert response.status_code == 200
    urls = response.context["urls"]
    assert "seed=" not in urls["get_artworks_with_params"]


@pytest.mark.integration
@pytest.mark.django_db
def test_same_seed_produces_consistent_order():
    """
    Test that two requests with same seed + filters return same IDs.

    This test verifies:
    - Core requirement: pagination must be consistent with same seed
    - Deterministic ordering for user experience

    Potential bugs this could catch:
    - Random ordering despite same seed
    - Non-deterministic SQL query
    """
    from artsearch.src.services.browse_service import get_random_artwork_ids
    from artsearch.models import ArtworkStats

    # Create test artworks in real database
    ArtworkStats.objects.create(
        museum_slug="smk", object_number="KMS1", searchable_work_types=["painting"]
    )
    ArtworkStats.objects.create(
        museum_slug="cma", object_number="1234", searchable_work_types=["painting"]
    )
    ArtworkStats.objects.create(
        museum_slug="rma", object_number="SK-A-1", searchable_work_types=["drawing"]
    )

    result1 = get_random_artwork_ids(
        museums=None,
        work_types=None,
        seed="fixed_seed_123",
        limit=10,
        offset=0,
    )

    result2 = get_random_artwork_ids(
        museums=None,
        work_types=None,
        seed="fixed_seed_123",
        limit=10,
        offset=0,
    )

    # Both calls should produce same result since seed is same
    assert result1 == result2
    assert len(result1) == 3


@pytest.mark.integration
@pytest.mark.django_db
def test_different_seeds_produce_different_order():
    """
    Test that two requests with different seeds return different order.

    This test verifies:
    - Each session should get unique random experience
    - Different seeds produce different orderings

    Potential bugs this could catch:
    - Seed not actually affecting ordering
    - Hardcoded order ignoring seed
    """
    from artsearch.src.services.browse_service import get_random_artwork_ids
    from artsearch.models import ArtworkStats

    # Create enough test artworks to make ordering differences visible
    for i in range(10):
        ArtworkStats.objects.create(
            museum_slug="smk",
            object_number=f"KMS{i}",
            searchable_work_types=["painting"],
        )

    result1 = get_random_artwork_ids(
        museums=None,
        work_types=None,
        seed="seed_one",
        limit=10,
        offset=0,
    )

    result2 = get_random_artwork_ids(
        museums=None,
        work_types=None,
        seed="seed_two",
        limit=10,
        offset=0,
    )

    # Different seeds should produce different ordering
    # (same items, different order)
    assert set(result1) == set(result2)  # Same items
    assert result1 != result2  # Different order


@pytest.mark.integration
@pytest.mark.django_db
def test_infinite_scroll_stops_when_no_more_results(
    mock_qdrant_service, mock_random_artwork_ids
):
    """
    Test that response doesn't include infinite scroll div when results empty.

    This test verifies:
    - Prevents infinite loading spinner at end of collection
    - No hx-trigger="revealed" when no results

    Potential bugs this could catch:
    - Infinite scroll continues after end of results
    - Empty pages keep triggering more requests
    """
    mock_random_artwork_ids.return_value = []
    mock_qdrant_service.get_items_by_ids.return_value = []

    client = Client()
    url = reverse("get-artworks") + "?offset=1000"

    response = client.get(url)

    assert response.status_code == 200
    html = response.content.decode()

    # When no results, the hx-trigger="revealed" div should not be present
    assert 'hx-trigger="revealed"' not in html


@pytest.mark.integration
@pytest.mark.django_db
def test_browse_mode_requires_seed():
    """
    Test that handle_search() raises ValueError when seed=None for browse.

    This test verifies:
    - Prevents bugs from forgetting to pass seed
    - Explicit error for missing required parameter

    Potential bugs this could catch:
    - Browse executed without seed causing non-deterministic pagination
    - Silent failures when seed missing
    """
    with pytest.raises(ValueError) as exc_info:
        handle_search(
            query=None,  # Browse mode (no query)
            offset=0,
            limit=25,
            museum_prefilter=None,
            work_type_prefilter=None,
            seed=None,  # Missing seed - should raise
        )

    assert "seed is required for browsing mode" in str(exc_info.value)
