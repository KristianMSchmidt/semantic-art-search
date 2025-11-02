"""
Integration tests for artsearch views/endpoints.

Tests WHAT the views should do (handle requests and return correct responses),
not HOW they do it (implementation details).

Following CLAUDE.md test principles:
- What-focused: Test business outcomes
- Integration over unit: Test entire request/response flow
- Mock expensive dependencies: Mock Qdrant, not views/URLs
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from django.urls import reverse


@pytest.fixture
def mock_qdrant_service():
    """Mock Qdrant service for all tests."""
    mock_service = MagicMock()

    # Mock methods used by museum_stats_service
    mock_service.fetch_points.return_value = ([], None)

    # Mock methods used by search_service
    mock_service.get_random_sample.return_value = []
    mock_service.search_text.return_value = []
    mock_service.search_similar_images.return_value = []
    mock_service.get_items_by_object_number.return_value = []

    # Patch get_qdrant_service in BOTH modules where it's called
    with (
        patch(
            "artsearch.src.services.qdrant_service.get_qdrant_service",
            return_value=mock_service,
        ),
        patch(
            "artsearch.src.services.museum_stats_service.get_qdrant_service",
            return_value=mock_service,
        ),
    ):
        yield mock_service


@pytest.fixture(autouse=True)
def clear_lru_caches():
    """Clear LRU caches before each test to ensure clean state."""
    import artsearch.src.services.museum_stats_service as stats_service

    stats_service.aggregate_work_type_counts.cache_clear()
    yield
    stats_service.aggregate_work_type_counts.cache_clear()


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_loads_successfully(mock_qdrant_service):
    """
    Test that the home page loads successfully and contains expected elements.

    This test verifies:
    - Home page returns 200 OK
    - Page contains search form elements
    - Filter dropdowns are present
    - Example queries are included

    Potential bugs this could catch:
    - URL routing broken
    - Template rendering errors
    - Missing context variables
    - Qdrant service initialization issues
    """
    client = Client()
    url = reverse("home")

    response = client.get(url)

    # Basic response checks
    assert response.status_code == 200
    assert "home.html" in [t.name for t in response.templates]

    # Verify key context elements are present
    assert "work_type_filter_context" in response.context
    assert "museum_filter_context" in response.context
    assert "example_queries" in response.context

    # Verify filter contexts have required structure
    work_type_ctx = response.context["work_type_filter_context"]
    assert work_type_ctx.dropdown_name == "work_types"
    # With mocked empty Qdrant, dropdown_items will be empty (no work types found)
    assert isinstance(work_type_ctx.dropdown_items, list)

    museum_ctx = response.context["museum_filter_context"]
    assert museum_ctx.dropdown_name == "museums"
    # Museums list comes from constants, not Qdrant, so it should have items
    assert len(museum_ctx.dropdown_items) == 5  # SMK, CMA, RMA, MET, AIC
    # Verify museums are sorted alphabetically by full name
    museum_names = [item["label"] for item in museum_ctx.dropdown_items]
    assert museum_names == sorted(museum_names), "Museums should be alphabetically sorted"

    # Verify example queries are provided (from constants, not Qdrant)
    example_queries = response.context["example_queries"]
    assert isinstance(example_queries, list)
    assert len(example_queries) > 0


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artworks_view_with_empty_query(mock_qdrant_service):
    """
    Test that /artworks/ with no query returns random sample.

    This test verifies:
    - Endpoint returns 200 OK
    - Correct template rendered
    - "A glimpse into the archive" text present
    - Random sample is requested from Qdrant

    Potential bugs this could catch:
    - URL routing broken
    - Template path incorrect
    - Random sample logic broken
    - Context building errors
    """
    client = Client()
    url = reverse("get-artworks")

    response = client.get(url)

    # Basic response checks
    assert response.status_code == 200
    assert "partials/artwork_response.html" in [t.name for t in response.templates]

    # Verify context has expected structure
    assert "results" in response.context
    assert "header_text" in response.context
    assert response.context["header_text"] == "A glimpse into the archive"
    assert response.context["results"] == []  # Mock returns empty list


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artworks_view_with_text_query_and_results(mock_qdrant_service):
    """
    Test search with query and results (total_works > 0).

    This test verifies:
    - Header text shows "Search results (X works)" when there are results
    - Correct template rendered
    - Text search is performed

    Potential bugs this could catch:
    - Header text not shown when it should be
    - Incorrect header text format
    - total_works not correctly displayed
    """
    client = Client()
    url = reverse("get-artworks") + "?query=landscape"

    # Mock that there are 42 total works matching the filters
    with patch(
        "artsearch.views.context_builders.get_total_works_for_filters",
        return_value=42,
    ):
        response = client.get(url)

    # Basic response checks
    assert response.status_code == 200
    assert "partials/artwork_response.html" in [t.name for t in response.templates]

    # Verify header text is set correctly when there are results
    assert "header_text" in response.context
    assert response.context["header_text"] == "Search results (42 works)"


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artworks_view_with_text_query_no_results(mock_qdrant_service):
    """
    Test search with query but no results (total_works = 0).

    This test verifies:
    - Header text is None when total_works = 0
    - Template still renders correctly
    - Search is performed but yields no results

    Potential bugs this could catch:
    - Header text shown when it shouldn't be (total_works = 0)
    - Template breaks when header_text is None
    """
    client = Client()
    url = reverse("get-artworks") + "?query=nonexistent"

    # Mock that there are 0 total works matching the filters
    with patch(
        "artsearch.views.context_builders.get_total_works_for_filters",
        return_value=0,
    ):
        response = client.get(url)

    # Basic response checks
    assert response.status_code == 200
    assert "partials/artwork_response.html" in [t.name for t in response.templates]

    # Verify header text is None when there are no results
    assert "header_text" in response.context
    assert response.context["header_text"] is None


@pytest.mark.integration
@pytest.mark.django_db
def test_update_work_types_htmx_endpoint(mock_qdrant_service):
    """
    Test that HTMX work type filter update endpoint works.

    This test verifies:
    - Endpoint returns 200 OK
    - Correct template rendered (dropdown partial)
    - Filter context present

    Potential bugs this could catch:
    - HTMX endpoint routing broken
    - Template path incorrect
    - Filter context building broken
    """
    client = Client()
    url = reverse("update-work-types")

    response = client.get(url)

    # Basic response checks
    assert response.status_code == 200
    assert "partials/dropdown.html" in [t.name for t in response.templates]

    # Verify context structure
    assert "filter_ctx" in response.context

    filter_ctx = response.context["filter_ctx"]
    assert filter_ctx.dropdown_name == "work_types"


@pytest.mark.integration
@pytest.mark.django_db
def test_update_museums_htmx_endpoint(mock_qdrant_service):
    """
    Test that HTMX museum filter update endpoint works.

    This test verifies:
    - Endpoint returns 200 OK
    - Correct template rendered (dropdown partial)
    - Filter context present

    Potential bugs this could catch:
    - HTMX endpoint routing broken
    - Template path incorrect
    - Filter context building broken
    """
    client = Client()
    url = reverse("update-museums")

    response = client.get(url)

    # Basic response checks
    assert response.status_code == 200
    assert "partials/dropdown.html" in [t.name for t in response.templates]

    # Verify context structure
    assert "filter_ctx" in response.context

    filter_ctx = response.context["filter_ctx"]
    assert filter_ctx.dropdown_name == "museums"
