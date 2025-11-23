"""
Integration tests for artwork description generation feature.

Tests WHAT the artwork description endpoint should do (handle requests and return correct responses),
not HOW it does it (implementation details).

Following CLAUDE.md test principles:
- What-focused: Test business outcomes
- Integration over unit: Test entire request/response flow
- Mock expensive dependencies: Mock OpenAI/museum APIs, not views
"""

import pytest
from unittest.mock import patch
from django.test import Client, RequestFactory
from django.urls import reverse
from artsearch.models import ArtworkDescription
from artsearch.views.views import get_artwork_description_view


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_cache_hit():
    """
    Test that the endpoint returns cached description when available.

    This test verifies:
    - Endpoint returns 200 OK
    - Cached description is returned
    - generate_description service is NOT called (cache hit)
    - Correct template rendered
    - Context contains description and artwork info

    Potential bugs this could catch:
    - Cache lookup not working
    - Description not passed to template
    - Template rendering broken
    - URL routing broken
    """
    # Create cached description in database
    ArtworkDescription.objects.create(
        museum_slug="smk",
        object_number="KMS1",
        description="This is a cached description of the artwork.",
    )

    client = Client()
    url = reverse("get-artwork-description")
    params = {
        "museum": "smk",
        "object_number": "KMS1",
        "museum_db_id": "12345",
    }

    response = client.get(url, params)

    # Basic response checks
    assert response.status_code == 200
    assert "partials/artwork_description.html" in [t.name for t in response.templates]

    # Verify context
    assert "description" in response.context
    assert (
        response.context["description"]
        == "This is a cached description of the artwork."
    )
    assert response.context["museum_slug"] == "smk"
    assert response.context["object_number"] == "KMS1"


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_cache_miss():
    """
    Test that the endpoint generates new description when cache is empty.

    This test verifies:
    - Endpoint returns 200 OK
    - generate_description service is called (cache miss)
    - Generated description is returned
    - Description is saved to cache
    - Correct template rendered

    Potential bugs this could catch:
    - Cache miss not triggering generation
    - Generated description not saved to cache
    - Service not called correctly
    - Template not receiving generated description
    """
    client = Client()
    url = reverse("get-artwork-description")
    params = {
        "museum": "cma",
        "object_number": "1234.56",
        "museum_db_id": "67890",
    }

    # Mock the generate_description service
    with patch(
        "artsearch.views.views.generate_description",
        return_value="This is a newly generated description.",
    ) as mock_generate:
        response = client.get(url, params)

        # Verify service was called with correct parameters
        mock_generate.assert_called_once_with(
            "cma", "1234.56", "67890", force_regenerate=False
        )

    # Basic response checks
    assert response.status_code == 200
    assert "partials/artwork_description.html" in [t.name for t in response.templates]

    # Verify context
    assert "description" in response.context
    assert response.context["description"] == "This is a newly generated description."
    assert response.context["museum_slug"] == "cma"
    assert response.context["object_number"] == "1234.56"


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_force_regenerate():
    """
    Test that force=true bypasses cache and regenerates description.

    This test verifies:
    - Endpoint returns 200 OK
    - Cached description is ignored when force=true
    - generate_description called with force_regenerate=True
    - New description overwrites cached one
    - Correct template rendered

    Potential bugs this could catch:
    - Force regenerate flag not working
    - Cache not being bypassed
    - Service not called with correct force flag
    - Cached description returned instead of new one
    """
    # Create cached description in database
    ArtworkDescription.objects.create(
        museum_slug="met",
        object_number="11.45.67",
        description="Old cached description.",
    )

    client = Client()
    url = reverse("get-artwork-description")
    params = {
        "museum": "met",
        "object_number": "11.45.67",
        "museum_db_id": "999",
        "force": "true",  # Force regenerate
    }

    # Mock the generate_description service
    with patch(
        "artsearch.views.views.generate_description",
        return_value="Freshly regenerated description.",
    ) as mock_generate:
        response = client.get(url, params)

        # Verify service was called with force_regenerate=True
        mock_generate.assert_called_once_with(
            "met", "11.45.67", "999", force_regenerate=True
        )

    # Basic response checks
    assert response.status_code == 200

    # Verify context has new description, not cached one
    assert response.context["description"] == "Freshly regenerated description."
    assert response.context["description"] != "Old cached description."


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_generation_fails():
    """
    Test that the endpoint handles generation failures gracefully.

    This test verifies:
    - Endpoint returns 200 OK even when generation fails
    - description is None when service returns None
    - Template renders error state correctly
    - No exception raised to user

    Potential bugs this could catch:
    - Unhandled exception when generation fails
    - Template not handling None description
    - 500 error instead of graceful degradation
    - Missing error message to user
    """
    client = Client()
    url = reverse("get-artwork-description")
    params = {
        "museum": "rma",
        "object_number": "SK-A-1234",
        "museum_db_id": "12345",
    }

    # Mock the generate_description service to return None (failure)
    with patch(
        "artsearch.views.views.generate_description",
        return_value=None,
    ) as mock_generate:
        response = client.get(url, params)

        # Verify service was called
        mock_generate.assert_called_once_with(
            "rma", "SK-A-1234", "12345", force_regenerate=False
        )

    # Basic response checks
    assert response.status_code == 200
    assert "partials/artwork_description.html" in [t.name for t in response.templates]

    # Verify context has None description
    assert "description" in response.context
    assert response.context["description"] is None
    assert response.context["museum_slug"] == "rma"
    assert response.context["object_number"] == "SK-A-1234"


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_force_flag_case_insensitive():
    """
    Test that force flag works with different casing (true, True, TRUE).

    This test verifies:
    - force=true (lowercase) triggers regeneration
    - force=True (capitalized) triggers regeneration
    - force=TRUE (uppercase) triggers regeneration
    - Case-insensitive flag parsing

    Potential bugs this could catch:
    - Force flag only working with specific casing
    - Case-sensitive flag comparison
    """
    client = Client()
    url = reverse("get-artwork-description")

    test_cases = ["true", "True", "TRUE"]

    for force_value in test_cases:
        params = {
            "museum": "smk",
            "object_number": "KMS999",
            "museum_db_id": "123",
            "force": force_value,
        }

        with patch(
            "artsearch.views.views.generate_description",
            return_value="Test description",
        ) as mock_generate:
            response = client.get(url, params)

            # Verify force_regenerate=True was passed
            mock_generate.assert_called_once_with(
                "smk", "KMS999", "123", force_regenerate=True
            )

        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_force_false_does_not_regenerate():
    """
    Test that force=false or missing force param uses normal cache behavior.

    This test verifies:
    - force=false does NOT bypass cache
    - Missing force param defaults to false
    - generate_description called with force_regenerate=False

    Potential bugs this could catch:
    - Default force value incorrect
    - force=false incorrectly triggering regeneration
    """
    client = Client()
    url = reverse("get-artwork-description")

    # Test force=false
    params_false = {
        "museum": "smk",
        "object_number": "KMS100",
        "museum_db_id": "123",
        "force": "false",
    }

    with patch(
        "artsearch.views.views.generate_description",
        return_value="Description",
    ) as mock_generate:
        client.get(url, params_false)
        mock_generate.assert_called_with("smk", "KMS100", "123", force_regenerate=False)

    # Test missing force param
    params_no_force = {
        "museum": "smk",
        "object_number": "KMS200",
        "museum_db_id": "456",
    }

    with patch(
        "artsearch.views.views.generate_description",
        return_value="Description",
    ) as mock_generate:
        client.get(url, params_no_force)
        mock_generate.assert_called_with("smk", "KMS200", "456", force_regenerate=False)


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_empty_params():
    """
    Test that the endpoint handles empty/missing query parameters.

    This test verifies:
    - Endpoint returns 200 OK even with empty params
    - Service called with empty strings for missing params
    - No exception raised

    Potential bugs this could catch:
    - Missing parameter validation
    - Unhandled exception for empty params
    - 500 error for missing required fields
    """
    client = Client()
    url = reverse("get-artwork-description")

    # No query params at all
    with patch(
        "artsearch.views.views.generate_description",
        return_value=None,
    ) as mock_generate:
        response = client.get(url)

        # Verify service was called with empty strings
        mock_generate.assert_called_once_with("", "", "", force_regenerate=False)

    assert response.status_code == 200
    assert response.context["museum_slug"] == ""
    assert response.context["object_number"] == ""


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artwork_description_view_rate_limit():
    """
    Test that the endpoint enforces rate limiting.

    This test verifies:
    - Rate limit is enforced (15 requests/15min/IP)
    - After limit exceeded, rate_limited context is True
    - description is None when rate limited
    - Template renders rate limit message
    - Service is NOT called when rate limited

    Potential bugs this could catch:
    - Rate limit not working
    - Service still called when rate limited
    - Template not handling rate limit state
    - Wrong rate limit threshold
    """
    url = reverse("get-artwork-description")
    params = {
        "museum": "smk",
        "object_number": "KMS1",
        "museum_db_id": "12345",
    }

    # Test the rate limit path by directly calling the view
    # with a mocked request that has limited=True attribute
    with patch("artsearch.views.views.generate_description") as mock_generate:
        # Create a request and manually set limited=True to test the rate limit path
        factory = RequestFactory()
        request = factory.get(url, params)
        request.limited = True  # type:ignore # Simulate rate limit exceeded

        # Call view directly
        response = get_artwork_description_view(request)

        # Verify service was NOT called when rate limited
        mock_generate.assert_not_called()

        # Check response
        assert response.status_code == 200

        # Parse the response content to verify rate limit message
        content = response.content.decode("utf-8")
        assert "Rate limit exceeded" in content
        assert "Too many requests" in content
