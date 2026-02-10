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

from artsearch.models import ExampleQuery, ArtMapData


@pytest.fixture
def example_queries(db):
    """Create example queries in the database for tests."""
    queries = ["Ship in a storm", "Reading child", "Cubism"]
    for query in queries:
        ExampleQuery.objects.create(query=query, is_active=True)
    return queries


@pytest.fixture
def mock_qdrant_service():
    """Mock Qdrant service for all tests."""
    mock_service = MagicMock()

    # Mock methods used by search_service and browse_service
    mock_service.get_items_by_ids.return_value = []
    mock_service.search_text.return_value = []
    mock_service.search_similar_images.return_value = []
    mock_service.get_items_by_object_number.return_value = []

    # Patch QdrantService where it's used (search_service and browse_service)
    # Also patch get_random_artwork_ids for browse mode tests
    with patch(
        "artsearch.src.services.search_service.QdrantService",
        return_value=mock_service,
    ), patch(
        "artsearch.src.services.browse_service.QdrantService",
        return_value=mock_service,
    ), patch(
        "artsearch.src.services.browse_service.get_random_artwork_ids",
        return_value=[],
    ):
        yield mock_service


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_loads_successfully(mock_qdrant_service, example_queries):
    """
    Test that the home page loads successfully and contains expected elements.

    This test verifies:
    - Home page returns 200 OK
    - Page contains search form elements
    - Filter dropdowns are present
    - Example queries are included (from database)

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
    assert museum_names == sorted(museum_names), (
        "Museums should be alphabetically sorted"
    )

    # Verify example queries are provided (from database via fixture)
    returned_queries = response.context["example_queries"]
    assert isinstance(returned_queries, list)
    assert len(returned_queries) > 0


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artworks_view_with_empty_query(mock_qdrant_service):
    """
    Test that /artworks/ with no query returns random sample.

    This test verifies:
    - Endpoint returns 200 OK
    - Correct template rendered
    - No header text on initial load (decluttered UI)
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
    assert response.context["header_text"] == ""
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


@pytest.mark.integration
@pytest.mark.django_db
def test_clear_cache_endpoint_requires_auth(mock_qdrant_service):
    """
    Test that /clear-cache endpoint requires admin authentication.

    This test verifies:
    - Endpoint redirects to login when not authenticated
    - Anonymous users cannot clear cache

    Potential bugs this could catch:
    - Missing authentication decorator
    - Cache cleared by non-admin users
    """
    client = Client()
    url = reverse("clear-cache")

    response = client.get(url)

    # Should redirect to login page (302) since user is not authenticated
    assert response.status_code == 302
    assert "/admin/login/" in response.url  # type: ignore


@pytest.mark.integration
@pytest.mark.django_db
def test_clear_cache_endpoint_clears_caches(mock_qdrant_service):
    """
    Test that /clear-cache endpoint successfully clears all LRU caches.

    This test verifies:
    - Endpoint returns 200 OK for admin user
    - Success message displayed
    - Caches are actually cleared

    Potential bugs this could catch:
    - Cache not actually cleared
    - Missing cache_clear() calls
    - Wrong response returned
    """
    from django.contrib.auth.models import User
    from artsearch.src.services import museum_stats_service

    # Create admin user
    admin_user = User.objects.create_superuser(
        username="admin", email="admin@test.com", password="testpass"
    )

    client = Client()
    client.force_login(admin_user)

    # Populate caches by calling cached functions
    museum_stats_service.get_work_type_names()
    museum_stats_service.aggregate_work_type_count_for_selected_museums(("smk",))
    museum_stats_service.aggregate_museum_count_for_selected_work_types(("painting",))
    museum_stats_service.get_total_works_for_filters(("smk",), ("painting",))

    # Verify caches have entries
    assert museum_stats_service.get_work_type_names.cache_info().currsize > 0
    assert (
        museum_stats_service.aggregate_work_type_count_for_selected_museums.cache_info().currsize
        > 0
    )
    assert (
        museum_stats_service.aggregate_museum_count_for_selected_work_types.cache_info().currsize
        > 0
    )
    assert museum_stats_service.get_total_works_for_filters.cache_info().currsize > 0

    # Clear cache via endpoint
    url = reverse("clear-cache")
    response = client.get(url)

    # Verify response
    assert response.status_code == 200
    assert b"Cleared" in response.content and b"caches successfully" in response.content

    # Verify all caches are cleared
    assert museum_stats_service.get_work_type_names.cache_info().currsize == 0
    assert (
        museum_stats_service.aggregate_work_type_count_for_selected_museums.cache_info().currsize
        == 0
    )
    assert (
        museum_stats_service.aggregate_museum_count_for_selected_work_types.cache_info().currsize
        == 0
    )
    assert museum_stats_service.get_total_works_for_filters.cache_info().currsize == 0


@pytest.mark.integration
@pytest.mark.django_db
def test_query_within_limit_succeeds(mock_qdrant_service):
    """
    Test that a query at exactly 500 characters works.

    This test verifies:
    - Query at max length (500 chars) is accepted
    - No error message returned
    - Search is performed normally

    Potential bugs this could catch:
    - Off-by-one error in length validation
    - Queries at boundary length incorrectly rejected
    """
    client = Client()
    # Create a query exactly at the 500 character limit
    query = "a" * 500
    url = reverse("get-artworks") + f"?query={query}"

    response = client.get(url)

    # Should succeed - no error message
    assert response.status_code == 200
    assert response.context.get("error_message") is None


@pytest.mark.integration
@pytest.mark.django_db
def test_query_exceeds_limit_returns_error(mock_qdrant_service):
    """
    Test that a query over 500 characters returns an error message.

    This test verifies:
    - Query over max length (501+ chars) is rejected
    - Error message is returned in context
    - Correct error message text

    Potential bugs this could catch:
    - Length validation not implemented
    - Wrong error message
    - Search performed despite invalid query
    """
    client = Client()
    # Create a query that exceeds the 500 character limit
    query = "a" * 501
    url = reverse("get-artworks") + f"?query={query}"

    response = client.get(url)

    # Should return error message
    assert response.status_code == 200
    assert response.context.get("error_message") == "Query too long (max 500 characters)"
    assert response.context.get("error_type") == "error"


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_returns_only_active_example_queries(mock_qdrant_service):
    """
    Test that only active example queries are returned on the home page.

    This test verifies:
    - Queries with is_active=True are included
    - Queries with is_active=False are excluded
    - The is_active flag filters correctly

    Potential bugs this could catch:
    - is_active filter not applied
    - All queries returned regardless of status
    - Filter logic inverted
    """
    # Create active and inactive queries
    ExampleQuery.objects.create(query="Active query", is_active=True)
    ExampleQuery.objects.create(query="Inactive query", is_active=False)

    client = Client()
    response = client.get(reverse("home"))

    queries = response.context["example_queries"]

    assert len(queries) == 1
    assert queries[0]["query"] == "Active query"


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_randomizes_example_queries(mock_qdrant_service):
    """
    Test that example queries are randomized on each page load.

    This test verifies:
    - Multiple requests produce different orderings
    - Randomization via random.sample() is working

    Potential bugs this could catch:
    - Queries always returned in same order
    - Randomization logic removed or broken
    - Database ordering overriding randomization
    """
    # Create several queries to make randomization statistically observable
    for i in range(10):
        ExampleQuery.objects.create(query=f"Query {i}", is_active=True)

    client = Client()

    # Make multiple requests and collect orderings
    orderings = []
    for _ in range(5):
        response = client.get(reverse("home"))
        order = tuple(q["query"] for q in response.context["example_queries"])
        orderings.append(order)

    # At least some orderings should differ (statistically very likely with 10 items)
    assert len(set(orderings)) > 1, "Expected different orderings across requests"


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_handles_no_example_queries(mock_qdrant_service):
    """
    Test that home page handles empty example queries gracefully.

    This test verifies:
    - Home page loads successfully with no queries in database
    - example_queries context is an empty list
    - No errors or crashes

    Potential bugs this could catch:
    - Crash when database has no queries
    - random.sample() failing on empty list
    - Template rendering errors with empty list
    """
    # Ensure no queries exist
    ExampleQuery.objects.all().delete()

    client = Client()
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert response.context["example_queries"] == []


@pytest.mark.integration
@pytest.mark.django_db
def test_art_map_data_view_returns_json_with_cache_headers(mock_qdrant_service):
    """
    Test that /map/data/ returns stored JSON with Cache-Control headers.

    Potential bugs this could catch:
    - Wrong content type
    - Missing Cache-Control header
    - Data not served correctly from database
    """
    ArtMapData.objects.create(data='{"count":1,"x":[0.5],"y":[0.5]}')

    client = Client()
    response = client.get(reverse("art-map-data"))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert response["Cache-Control"] == "public, max-age=86400"
    assert response.content == b'{"count":1,"x":[0.5],"y":[0.5]}'


@pytest.mark.integration
@pytest.mark.django_db
def test_art_map_data_view_returns_404_when_no_data(mock_qdrant_service):
    """
    Test that /map/data/ returns 404 when no map data exists.

    Potential bugs this could catch:
    - Server error instead of clean 404
    - Wrong error message format
    """
    client = Client()
    response = client.get(reverse("art-map-data"))

    assert response.status_code == 404
    assert response.json() == {"error": "No map data available"}


@pytest.mark.integration
@pytest.mark.django_db
def test_art_map_view_passes_version_to_template(mock_qdrant_service):
    """
    Test that /map/ passes map_data_version to the template for cache-busting.

    Potential bugs this could catch:
    - Missing version in template context
    - Version format incorrect
    """
    map_data = ArtMapData.objects.create(data='{"count":0}')

    client = Client()
    response = client.get(reverse("art-map"))

    assert response.status_code == 200
    assert response.context["map_data_version"] == map_data.version
    assert len(response.context["map_data_version"]) == 14  # YYYYMMDDHHmmss


@pytest.mark.integration
@pytest.mark.django_db
def test_art_map_view_handles_no_data(mock_qdrant_service):
    """
    Test that /map/ renders correctly when no map data exists.

    Potential bugs this could catch:
    - Server error when no ArtMapData rows exist
    - Template crash on empty version string
    """
    client = Client()
    response = client.get(reverse("art-map"))

    assert response.status_code == 200
    assert response.context["map_data_version"] == ""
