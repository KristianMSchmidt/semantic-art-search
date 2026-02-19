"""
Integration tests for the API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from qdrant_client import models


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


def _make_scored_point(payload):
    return models.ScoredPoint(
        id="fake-id",
        version=1,
        score=1.0,
        payload=payload,
    )


@pytest.fixture
def mock_qdrant_service():
    mock_service = MagicMock()
    with patch("artsearch.api.views.qdrant_service", mock_service):
        yield mock_service


@pytest.mark.integration
def test_artwork_detail_returns_payload_with_urls(mock_qdrant_service):
    mock_qdrant_service.get_items_by_object_number.return_value = [
        _make_scored_point(SAMPLE_PAYLOAD)
    ]

    client = Client()
    response = client.get("/api/artworks/smk/KMS1/")

    assert response.status_code == 200
    data = response.json()

    # Raw payload fields are present
    assert data["museum"] == "smk"
    assert data["object_number"] == "KMS1"
    assert data["title"] == "Portrait of a Young Woman"
    assert data["artists"] == ["Johannes Vermeer"]
    assert data["production_date"] == "1665-1667"
    assert data["work_types"] == ["painting"]
    assert data["searchable_work_types"] == ["painting"]
    assert data["museum_db_id"] == "abc123"

    # Computed URLs are present
    assert "thumbnail_url" in data
    assert "source_url" in data
    assert "api_url" in data

    # Qdrant was called with correct args
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
