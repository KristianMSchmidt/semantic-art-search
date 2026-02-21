"""
Integration tests for the API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from qdrant_client import models

from artsearch.src.constants.museums import SUPPORTED_MUSEUMS
from artsearch.src.constants.work_types import SEARCHABLE_WORK_TYPES


# ---- Museums Endpoint Tests ----


@pytest.mark.integration
def test_museums_returns_all_museums():
    client = Client()
    response = client.get("/api/museums/")

    assert response.status_code == 200
    data = response.json()

    assert len(data["museums"]) == len(SUPPORTED_MUSEUMS)
    for museum in data["museums"]:
        assert "slug" in museum
        assert "full_name" in museum
        assert len(museum) == 2  # only slug and full_name, no short_name


@pytest.mark.integration
def test_museums_contains_expected_slugs():
    client = Client()
    response = client.get("/api/museums/")

    slugs = [m["slug"] for m in response.json()["museums"]]
    assert "smk" in slugs
    assert "met" in slugs


# ---- Work Types Endpoint Tests ----


@pytest.mark.integration
def test_work_types_returns_all_searchable_types():
    client = Client()
    response = client.get("/api/work-types/")

    assert response.status_code == 200
    data = response.json()

    assert set(data["work_types"]) == SEARCHABLE_WORK_TYPES


@pytest.mark.integration
def test_work_types_returns_sorted():
    client = Client()
    response = client.get("/api/work-types/")

    work_types = response.json()["work_types"]
    assert work_types == sorted(work_types)


# ---- Artwork Detail Tests ----


SAMPLE_PAYLOAD = {
    "museum": "smk",
    "object_number": "KMS1",
    "museum_db_id": "abc123",
    "title": "Portrait of a Young Woman",
    "artists": ["Johannes Vermeer"],
    "production_date": "1665-1667",
    "work_types": ["painting"],
    "searchable_work_types": ["painting"],
}

FORMATTED_PAYLOAD = {
    "title": "Portrait of a Young Woman",
    "artist": "Johannes Vermeer",
    "work_types": ["Painting"],
    "thumbnail_url": "https://example.com/thumb.jpg",
    "production_date": "1665-1667",
    "object_number": "KMS1",
    "museum": "Statens Museum for Kunst",
    "museum_slug": "smk",
    "museum_db_id": "abc123",
    "source_url": "https://example.com/source",
    "api_url": "https://example.com/api",
    "find_similar_query": "smk:KMS1",
}


def _make_scored_point(payload, score=1.0):
    return models.ScoredPoint(
        id="fake-id",
        version=1,
        score=score,
        payload=payload,
    )


@pytest.fixture
def mock_qdrant_service():
    mock_service = MagicMock()
    with patch("artsearch.api.views.qdrant_service", mock_service):
        yield mock_service


# ---- Artwork Detail Tests ----


@pytest.mark.integration
def test_artwork_detail_returns_formatted_payload(mock_qdrant_service):
    mock_qdrant_service.get_items_by_object_number.return_value = [
        _make_scored_point(SAMPLE_PAYLOAD)
    ]

    with patch("artsearch.api.views.format_payload", return_value=FORMATTED_PAYLOAD):
        client = Client()
        response = client.get("/api/artworks/smk/KMS1/")

    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "Portrait of a Young Woman"
    assert data["artist"] == "Johannes Vermeer"
    assert data["museum"] == "Statens Museum for Kunst"
    assert data["museum_slug"] == "smk"
    assert data["work_types"] == ["Painting"]
    assert data["find_similar_query"] == "smk:KMS1"
    assert "thumbnail_url" in data
    assert "source_url" in data
    assert "api_url" in data

    mock_qdrant_service.get_items_by_object_number.assert_called_once_with(
        object_number="KMS1",
        object_museum="smk",
        with_payload=True,
        limit=1,
    )


@pytest.mark.integration
def test_artwork_detail_returns_404_when_not_found(mock_qdrant_service):
    mock_qdrant_service.get_items_by_object_number.return_value = []

    client = Client()
    response = client.get("/api/artworks/smk/NONEXISTENT/")

    assert response.status_code == 404
    assert response.json() == {"error": "Artwork not found"}


@pytest.mark.integration
def test_artwork_detail_returns_404_when_payload_is_none(mock_qdrant_service):
    mock_qdrant_service.get_items_by_object_number.return_value = [
        _make_scored_point(None)
    ]

    client = Client()
    response = client.get("/api/artworks/smk/KMS1/")

    assert response.status_code == 404
    assert response.json() == {"error": "Artwork not found"}


# ---- Search Tests ----


FORMATTED_SEARCH_RESULT = {**FORMATTED_PAYLOAD, "score": 0.85}

SAMPLE_SEARCH_RESULTS = {
    "results": [FORMATTED_SEARCH_RESULT],
    "header_text": "Search results (125 works)",
    "error_message": None,
    "error_type": None,
    "total_works": 125,
}


@pytest.fixture
def mock_search_deps():
    """Mock all search view dependencies."""
    with patch(
        "artsearch.api.views.handle_search",
        return_value=SAMPLE_SEARCH_RESULTS,
    ) as mock_search:
        yield {
            "handle_search": mock_search,
        }


@pytest.mark.integration
def test_search_returns_results(mock_search_deps):
    client = Client()
    response = client.get("/api/search/?query=landscape")

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "landscape"
    assert data["total_works"] == 125
    assert data["offset"] == 0
    assert data["limit"] == 24
    assert len(data["results"]) == 1
    assert data["results"][0]["score"] == 0.85
    assert data["results"][0]["title"] == "Portrait of a Young Woman"


@pytest.mark.integration
def test_search_missing_query():
    client = Client()
    response = client.get("/api/search/")

    assert response.status_code == 400
    assert response.json() == {"error": "query parameter is required"}


@pytest.mark.integration
def test_search_empty_query():
    client = Client()
    response = client.get("/api/search/?query=")

    assert response.status_code == 400
    assert response.json() == {"error": "query parameter is required"}


@pytest.mark.integration
def test_search_whitespace_only_query():
    client = Client()
    response = client.get("/api/search/?query=%20%20")

    assert response.status_code == 400
    assert response.json() == {"error": "query parameter is required"}


@pytest.mark.integration
def test_search_query_too_long():
    client = Client()
    long_query = "a" * 501
    response = client.get(f"/api/search/?query={long_query}")

    assert response.status_code == 400
    assert "too long" in response.json()["error"].lower()


@pytest.mark.integration
def test_search_rate_limited(mock_search_deps):
    client = Client()
    with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
        response = client.get("/api/search/?query=landscape")

    assert response.status_code == 429
    assert "too many" in response.json()["error"].lower()


@pytest.mark.integration
def test_search_passes_filters(mock_search_deps):
    client = Client()
    response = client.get(
        "/api/search/?query=landscape&museums=smk&museums=met&work_types=painting"
    )

    assert response.status_code == 200

    mock_search_deps["handle_search"].assert_called_once_with(
        query="landscape",
        offset=0,
        limit=24,
        museums=["smk", "met"],
        work_types=["painting"],
        embedding_model="auto",
    )


@pytest.mark.integration
def test_search_no_filters_passes_none(mock_search_deps):
    client = Client()
    response = client.get("/api/search/?query=landscape")

    assert response.status_code == 200

    mock_search_deps["handle_search"].assert_called_once_with(
        query="landscape",
        offset=0,
        limit=24,
        museums=None,
        work_types=None,
        embedding_model="auto",
    )


@pytest.mark.integration
def test_search_passes_model_param(mock_search_deps):
    client = Client()
    response = client.get("/api/search/?query=landscape&model=clip")

    assert response.status_code == 200

    call_kwargs = mock_search_deps["handle_search"].call_args[1]
    assert call_kwargs["embedding_model"] == "clip"


@pytest.mark.integration
def test_search_returns_error_from_search_service(mock_search_deps):
    mock_search_deps["handle_search"].return_value = {
        "results": [],
        "header_text": None,
        "error_message": "An unexpected error occurred. Please try again.",
        "error_type": "error",
    }

    client = Client()
    response = client.get("/api/search/?query=landscape")

    assert response.status_code == 400
    assert (
        response.json()["error"] == "An unexpected error occurred. Please try again."
    )


@pytest.mark.integration
def test_search_offset_and_limit(mock_search_deps):
    client = Client()
    response = client.get("/api/search/?query=landscape&offset=10&limit=5")

    assert response.status_code == 200
    data = response.json()

    assert data["offset"] == 10
    assert data["limit"] == 5

    call_kwargs = mock_search_deps["handle_search"].call_args[1]
    assert call_kwargs["offset"] == 10
    assert call_kwargs["limit"] == 5


@pytest.mark.integration
def test_search_limit_capped_at_24(mock_search_deps):
    client = Client()
    response = client.get("/api/search/?query=landscape&limit=100")

    assert response.status_code == 200
    data = response.json()

    assert data["limit"] == 24


# ---- Similar Artworks Tests ----


SAMPLE_SIMILAR_RESULTS = {
    "results": [FORMATTED_SEARCH_RESULT],
    "header_text": "Search results (125 works)",
    "error_message": None,
    "error_type": None,
    "total_works": 125,
}


@pytest.fixture
def mock_similar_deps():
    """Mock all similar view dependencies."""
    with patch(
        "artsearch.api.views.handle_search",
        return_value=SAMPLE_SIMILAR_RESULTS,
    ) as mock_search:
        yield {"handle_search": mock_search}


@pytest.mark.integration
def test_similar_returns_results(mock_similar_deps):
    client = Client()
    response = client.get("/api/artworks/smk/KMS1/similar/")

    assert response.status_code == 200
    data = response.json()

    assert data["museum_slug"] == "smk"
    assert data["object_number"] == "KMS1"
    assert data["total_works"] == 125
    assert data["offset"] == 0
    assert data["limit"] == 24
    assert len(data["results"]) == 1
    assert data["results"][0]["score"] == 0.85


@pytest.mark.integration
def test_similar_calls_handle_search_with_correct_query(mock_similar_deps):
    client = Client()
    client.get("/api/artworks/smk/KMS1/similar/")

    mock_similar_deps["handle_search"].assert_called_once_with(
        query="smk:KMS1",
        offset=0,
        limit=24,
        museums=None,
        work_types=None,
        embedding_model="auto",
    )


@pytest.mark.integration
def test_similar_passes_filters(mock_similar_deps):
    client = Client()
    client.get("/api/artworks/smk/KMS1/similar/?museums=met&work_types=painting")

    mock_similar_deps["handle_search"].assert_called_once_with(
        query="smk:KMS1",
        offset=0,
        limit=24,
        museums=["met"],
        work_types=["painting"],
        embedding_model="auto",
    )


@pytest.mark.integration
def test_similar_passes_offset_and_limit(mock_similar_deps):
    client = Client()
    response = client.get("/api/artworks/smk/KMS1/similar/?offset=10&limit=5")

    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 10
    assert data["limit"] == 5

    call_kwargs = mock_similar_deps["handle_search"].call_args[1]
    assert call_kwargs["offset"] == 10
    assert call_kwargs["limit"] == 5


@pytest.mark.integration
def test_similar_limit_capped_at_24(mock_similar_deps):
    client = Client()
    response = client.get("/api/artworks/smk/KMS1/similar/?limit=100")

    assert response.status_code == 200
    assert response.json()["limit"] == 24


@pytest.mark.integration
def test_similar_returns_404_when_artwork_not_found(mock_similar_deps):
    mock_similar_deps["handle_search"].return_value = {
        "results": [],
        "header_text": None,
        "error_message": "No artworks found in the database from Statens Museum for Kunst with the inventory number NONEXISTENT.",
        "error_type": "warning",
        "total_works": 0,
    }

    client = Client()
    response = client.get("/api/artworks/smk/NONEXISTENT/similar/")

    assert response.status_code == 404
    assert "No artworks found" in response.json()["error"]


@pytest.mark.integration
def test_similar_rate_limited(mock_similar_deps):
    client = Client()
    with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
        response = client.get("/api/artworks/smk/KMS1/similar/")

    assert response.status_code == 429
    assert "too many" in response.json()["error"].lower()
