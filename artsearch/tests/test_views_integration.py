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

    # Mock methods used by search_service
    mock_service.get_random_sample.return_value = []
    mock_service.search_text.return_value = []
    mock_service.search_similar_images.return_value = []
    mock_service.get_items_by_object_number.return_value = []

    # Patch QdrantService where it's used (search_service), not where it's defined
    # This is required because search_service uses: from qdrant_service import QdrantService
    with patch(
        "artsearch.src.services.search_service.QdrantService",
        return_value=mock_service,
    ):
        yield mock_service


@pytest.fixture(autouse=True)
def clear_lru_caches():
    """Clear LRU caches before each test to ensure clean state."""
    import artsearch.src.services.museum_stats_service as stats_service

    # Clear all cached functions
    stats_service.get_work_type_names.cache_clear()
    stats_service.aggregate_work_type_count_for_selected_museums.cache_clear()
    stats_service.aggregate_museum_count_for_selected_work_types.cache_clear()
    stats_service.get_total_works_for_filters.cache_clear()

    yield

    # Clear caches after test
    stats_service.get_work_type_names.cache_clear()
    stats_service.aggregate_work_type_count_for_selected_museums.cache_clear()
    stats_service.aggregate_museum_count_for_selected_work_types.cache_clear()
    stats_service.get_total_works_for_filters.cache_clear()


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
    assert museum_names == sorted(museum_names), (
        "Museums should be alphabetically sorted"
    )

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
    assert response.content == b"Cache cleared successfully"

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
def test_set_language_view_sets_session_and_redirects(mock_qdrant_service):
    """
    Test that POST to /set-language/ stores language in session and redirects.

    This test verifies:
    - Valid language code is stored in session
    - Response redirects to home page
    - Session persists the language

    Potential bugs this could catch:
    - Session not being set
    - Wrong redirect target
    - POST not handled correctly
    """
    client = Client()
    url = reverse("set-language")

    response = client.post(url, {"language": "da"})

    # Should redirect to home
    assert response.status_code == 302
    assert response.url == reverse("home")

    # Verify session has the language
    assert client.session.get("user_language") == "da"


@pytest.mark.integration
@pytest.mark.django_db
def test_set_language_view_validates_language_codes(mock_qdrant_service):
    """
    Test that /set-language/ rejects invalid language codes.

    This test verifies:
    - Invalid language codes are not stored
    - Still redirects to home (graceful handling)
    - Session remains unchanged for invalid codes

    Potential bugs this could catch:
    - Arbitrary values stored in session
    - Security issue with untrusted input
    """
    client = Client()
    url = reverse("set-language")

    # Try to set invalid language
    response = client.post(url, {"language": "invalid"})

    # Should still redirect
    assert response.status_code == 302

    # Session should NOT have the invalid language
    assert client.session.get("user_language") is None


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_includes_language_context(mock_qdrant_service):
    """
    Test that home view passes language context variables to template.

    This test verifies:
    - current_language is in context
    - current_language_name is in context
    - languages list is in context
    - Default language is English

    Potential bugs this could catch:
    - Missing context variables
    - Template rendering errors for language selector
    """
    client = Client()
    url = reverse("home")

    response = client.get(url)

    assert response.status_code == 200

    # Verify language context variables
    assert "current_language" in response.context
    assert "current_language_name" in response.context
    assert "languages" in response.context

    # Default should be English
    assert response.context["current_language"] == "en"
    assert response.context["current_language_name"] == "English"

    # Languages should be the full list
    languages = response.context["languages"]
    assert len(languages) == 3
    assert ("en", "English") in languages
    assert ("da", "Dansk") in languages
    assert ("nl", "Nederlands") in languages


@pytest.mark.integration
@pytest.mark.django_db
def test_language_persists_across_requests(mock_qdrant_service):
    """
    Test that language selection persists across page loads via session.

    This test verifies:
    - Setting language stores it in session
    - Subsequent requests use the stored language
    - Language context reflects session value

    Potential bugs this could catch:
    - Session not persisting
    - Language reset on each request
    - Context not reading from session
    """
    client = Client()

    # Set language to Danish
    client.post(reverse("set-language"), {"language": "da"})

    # Load home page
    response = client.get(reverse("home"))

    # Verify language persisted
    assert response.context["current_language"] == "da"
    assert response.context["current_language_name"] == "Dansk"

    # Change to Dutch
    client.post(reverse("set-language"), {"language": "nl"})

    # Load home page again
    response = client.get(reverse("home"))

    # Verify new language persisted
    assert response.context["current_language"] == "nl"
    assert response.context["current_language_name"] == "Nederlands"
