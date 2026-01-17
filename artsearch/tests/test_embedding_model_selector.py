"""
Tests for embedding model selector functionality.

Tests the ability to choose between CLIP and Jina embedding models for search.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from django.urls import reverse
from django.http import QueryDict

from artsearch.src.constants.embedding_models import (
    EMBEDDING_MODELS,
    resolve_embedding_model,
)
from artsearch.views.context_builders import SearchParams, make_url_with_params


@pytest.fixture
def mock_qdrant_service():
    """Mock Qdrant service for all tests."""
    mock_service = MagicMock()

    mock_service.get_random_sample.return_value = []
    mock_service.search_text.return_value = []
    mock_service.search_similar_images.return_value = []
    mock_service.get_items_by_object_number.return_value = []

    with patch(
        "artsearch.src.services.search_service.QdrantService",
        return_value=mock_service,
    ):
        yield mock_service


@pytest.fixture(autouse=True)
def clear_lru_caches():
    """Clear LRU caches before each test to ensure clean state."""
    import artsearch.src.services.museum_stats_service as stats_service

    stats_service.get_work_type_names.cache_clear()
    stats_service.aggregate_work_type_count_for_selected_museums.cache_clear()
    stats_service.aggregate_museum_count_for_selected_work_types.cache_clear()
    stats_service.get_total_works_for_filters.cache_clear()

    yield

    stats_service.get_work_type_names.cache_clear()
    stats_service.aggregate_work_type_count_for_selected_museums.cache_clear()
    stats_service.aggregate_museum_count_for_selected_work_types.cache_clear()
    stats_service.get_total_works_for_filters.cache_clear()


# =============================================================================
# Unit Tests: resolve_embedding_model()
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "input_model,expected",
    [
        ("auto", "clip"),
        ("clip", "clip"),
        ("jina", "jina"),
    ],
)
def test_resolve_embedding_model(input_model, expected):
    """Test that resolve_embedding_model correctly resolves model values."""
    result = resolve_embedding_model(input_model)
    assert result == expected


# =============================================================================
# Unit Tests: SearchParams.selected_embedding_model
# =============================================================================


class MockRequest:
    """Simple mock request with GET parameters."""

    def __init__(self, get_params: dict | None = None):
        self.GET = QueryDict(mutable=True)
        if get_params:
            for key, value in get_params.items():
                if isinstance(value, list):
                    self.GET.setlist(key, value)
                else:
                    self.GET[key] = value


@pytest.mark.unit
@pytest.mark.parametrize(
    "model_param,expected",
    [
        ("auto", "auto"),
        ("clip", "clip"),
        ("jina", "jina"),
    ],
)
def test_search_params_selected_embedding_model_valid_values(model_param, expected):
    """Test that SearchParams correctly extracts valid model values from query params."""
    request = MockRequest({"model": model_param})
    params = SearchParams(request=request)  # type: ignore
    assert params.selected_embedding_model == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "get_params,expected",
    [
        ({"model": "invalid"}, "auto"),  # Invalid value defaults to auto
        ({}, "auto"),  # No param defaults to auto
    ],
)
def test_search_params_selected_embedding_model_invalid_defaults_to_auto(
    get_params, expected
):
    """Test that invalid or missing model param defaults to 'auto'."""
    request = MockRequest(get_params)
    params = SearchParams(request=request)  # type: ignore
    assert params.selected_embedding_model == expected


# =============================================================================
# Integration Tests: URL Building
# =============================================================================


@pytest.mark.unit
def test_make_url_with_params_excludes_model_when_auto():
    """Test that URLs with embedding_model='auto' don't include model param."""
    url = make_url_with_params(
        url_name="get-artworks",
        query="test",
        embedding_model="auto",
    )
    assert "model=" not in url
    assert "query=test" in url


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,expected_param",
    [
        ("clip", "model=clip"),
        ("jina", "model=jina"),
    ],
)
def test_make_url_with_params_includes_model_when_not_auto(model, expected_param):
    """Test that URLs with non-auto embedding_model include the model param."""
    url = make_url_with_params(
        url_name="get-artworks",
        query="test",
        embedding_model=model,
    )
    assert expected_param in url


# =============================================================================
# Integration Tests: Views
# =============================================================================


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_includes_embedding_models_in_context(mock_qdrant_service):
    """Test that home view includes embedding models in context."""
    client = Client()
    url = reverse("home")

    response = client.get(url)

    assert response.status_code == 200
    assert "embedding_models" in response.context
    assert response.context["embedding_models"] == EMBEDDING_MODELS
    assert "selected_model" in response.context
    assert response.context["selected_model"] == "auto"


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_param,expected",
    [
        ("jina", "jina"),
        ("clip", "clip"),
    ],
)
def test_home_view_selected_model_from_query_param(
    mock_qdrant_service, model_param, expected
):
    """Test that home view correctly reads model from query param."""
    client = Client()
    url = reverse("home") + f"?model={model_param}"

    response = client.get(url)

    assert response.status_code == 200
    assert response.context["selected_model"] == expected


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artworks_view_resolves_auto_to_clip(mock_qdrant_service):
    """Test that search with model=auto calls Qdrant with embedding_model='clip'."""
    client = Client()
    url = reverse("get-artworks") + "?query=landscape&model=auto"

    with patch(
        "artsearch.views.context_builders.get_total_works_for_filters",
        return_value=10,
    ):
        client.get(url)

    # Check that search_text was called with embedding_model="clip"
    mock_qdrant_service.search_text.assert_called_once()
    _, kwargs = mock_qdrant_service.search_text.call_args
    assert kwargs["embedding_model"] == "clip"


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize("model", ["jina", "clip"])
def test_get_artworks_view_passes_explicit_model_to_search(mock_qdrant_service, model):
    """Test that search with explicit model passes it to Qdrant service."""
    client = Client()
    url = reverse("get-artworks") + f"?query=landscape&model={model}"

    with patch(
        "artsearch.views.context_builders.get_total_works_for_filters",
        return_value=10,
    ):
        client.get(url)

    mock_qdrant_service.search_text.assert_called_once()
    _, kwargs = mock_qdrant_service.search_text.call_args
    assert kwargs["embedding_model"] == model


# =============================================================================
# Integration Tests: Qdrant Service
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,expected_vector_name",
    [
        ("clip", "image_clip"),
        ("jina", "image_jina"),
    ],
)
def test_qdrant_service_search_text_uses_correct_vector_name(
    model, expected_vector_name
):
    """Test that QdrantService uses the correct vector name for each model."""
    from artsearch.src.services.qdrant_service import (
        QdrantService,
        SearchFunctionArguments,
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.points = []
    mock_client.query_points.return_value = mock_response

    service = QdrantService(collection_name="test", qdrant_client=mock_client)

    search_args = SearchFunctionArguments(
        query="test query",
        limit=10,
        offset=0,
        work_type_prefilter=None,
        museum_prefilter=None,
    )

    # Mock the embedder to return a dummy vector
    with patch(
        "artsearch.src.services.qdrant_service.get_clip_embedder"
    ) as mock_clip, patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina:
        mock_embedder = MagicMock()
        mock_embedder.generate_text_embedding.return_value = [0.1] * 768
        mock_clip.return_value = mock_embedder
        mock_jina.return_value = mock_embedder

        service.search_text(search_args, embedding_model=model)

    # Check that query_points was called with the correct 'using' parameter
    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs["using"] == expected_vector_name


@pytest.mark.unit
def test_qdrant_service_search_text_selects_correct_embedder():
    """Test that QdrantService selects CLIP embedder for 'clip' and Jina for 'jina'."""
    from artsearch.src.services.qdrant_service import (
        QdrantService,
        SearchFunctionArguments,
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.points = []
    mock_client.query_points.return_value = mock_response

    service = QdrantService(collection_name="test", qdrant_client=mock_client)

    search_args = SearchFunctionArguments(
        query="test query",
        limit=10,
        offset=0,
        work_type_prefilter=None,
        museum_prefilter=None,
    )

    # Test CLIP model
    with patch(
        "artsearch.src.services.qdrant_service.get_clip_embedder"
    ) as mock_clip, patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina:
        mock_clip_embedder = MagicMock()
        mock_clip_embedder.generate_text_embedding.return_value = [0.1] * 768
        mock_clip.return_value = mock_clip_embedder

        mock_jina_embedder = MagicMock()
        mock_jina_embedder.generate_text_embedding.return_value = [0.2] * 768
        mock_jina.return_value = mock_jina_embedder

        service.search_text(search_args, embedding_model="clip")

        mock_clip.assert_called_once()
        mock_jina.assert_not_called()
        mock_clip_embedder.generate_text_embedding.assert_called_once_with("test query")

    # Test Jina model
    with patch(
        "artsearch.src.services.qdrant_service.get_clip_embedder"
    ) as mock_clip, patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina:
        mock_clip_embedder = MagicMock()
        mock_clip_embedder.generate_text_embedding.return_value = [0.1] * 768
        mock_clip.return_value = mock_clip_embedder

        mock_jina_embedder = MagicMock()
        mock_jina_embedder.generate_text_embedding.return_value = [0.2] * 768
        mock_jina.return_value = mock_jina_embedder

        service.search_text(search_args, embedding_model="jina")

        mock_jina.assert_called_once()
        mock_clip.assert_not_called()
        mock_jina_embedder.generate_text_embedding.assert_called_once_with("test query")
