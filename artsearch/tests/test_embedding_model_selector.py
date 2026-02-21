"""
Tests for embedding model selector functionality.

Tests the ability to choose between CLIP and Jina embedding models for search.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client, RequestFactory
from django.urls import reverse

from artsearch.src.constants.embedding_models import (
    EMBEDDING_MODELS,
    resolve_embedding_model,
    is_art_historical_query,
)
from artsearch.views.context_builders import SearchParams, make_url_with_params


@pytest.fixture
def mock_qdrant_service():
    """Mock Qdrant service for all tests."""
    mock_service = MagicMock()

    mock_service.get_items_by_ids.return_value = []
    mock_service.search_text.return_value = []
    mock_service.search_similar_images.return_value = []
    mock_service.get_items_by_object_number.return_value = []

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


# =============================================================================
# Unit Tests: resolve_embedding_model()
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "input_model,expected",
    [
        ("clip", "clip"),
        ("jina", "jina"),
    ],
)
def test_resolve_embedding_model_explicit(input_model, expected):
    """Test that explicit model choices are returned as-is."""
    result = resolve_embedding_model(input_model)
    assert result == expected


@pytest.mark.unit
def test_resolve_embedding_model_auto_defaults_to_jina():
    """Test that auto resolves to jina for non-art-historical queries."""
    result = resolve_embedding_model("auto")
    assert result == "jina"


@pytest.mark.unit
def test_resolve_embedding_model_auto_similarity_search_uses_jina():
    """Test that similarity search always uses Jina."""
    result = resolve_embedding_model("auto", is_similarity_search=True, query="impressionism")
    assert result == "jina"


@pytest.mark.unit
def test_resolve_embedding_model_auto_art_historical_uses_clip():
    """Test that art historical queries use CLIP."""
    result = resolve_embedding_model("auto", query="impressionism paintings")
    assert result == "clip"


@pytest.mark.unit
def test_resolve_embedding_model_auto_non_art_uses_jina():
    """Test that non-art queries use Jina."""
    result = resolve_embedding_model("auto", query="cat sitting on chair")
    assert result == "jina"


# =============================================================================
# Unit Tests: is_art_historical_query()
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "query",
    [
        # Art movement keywords
        "impressionism",
        "Impressionism",  # case insensitive
        "IMPRESSIONISM",  # case insensitive
        "baroque paintings",
        "art nouveau poster",
        "cubism and futurism",
        "abstract expressionism",
        "pop art style",
        "pre-raphaelite brotherhood",
        "ukiyo-e prints",
        "harlem renaissance artists",
        # Fauvism and Cubism variations
        "fauvism",
        "Fauvism",
        "FAUVISM",
        "fauvism paintings",
        "the fauvism movement",
        "cubism",
        "Cubism",
        "CUBISM",
        "cubism art",
        "analytical cubism",
        "synthetic cubism",
        # Style patterns - "in the style of"
        "in the style of Monet",
        "painting in the style of the Dutch masters",
        # Style patterns - *ist (adjective forms of movements)
        "impressionist bridge",
        "cubist portrait",
        "surrealist dream",
        "realist landscape",
        "expressionist painting",
        # Style patterns - *istic
        "expressionistic brushwork",
        "impressionistic landscape",
        "cubistic forms",
        "fauvistic colors",  # *istic pattern
        # Style patterns - *esque
        "Rembrandtesque lighting",
        "Turneresque seascape",
    ],
)
def test_is_art_historical_query_returns_true(query):
    """Test that art historical queries are correctly detected."""
    assert is_art_historical_query(query) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "query",
    [
        # General queries
        "cat",
        "sunset over ocean",
        "portrait of a woman",
        "flowers in a vase",
        "landscape with mountains",
        # Words ending in -ist that aren't art movements
        "list of paintings",
        "misty morning",
        # Words that shouldn't trigger detection (-esque excluded words)
        "a picturesque village",  # "picturesque" is excluded
        "grotesque monster",  # "grotesque" is excluded
        "burlesque show",  # "burlesque" is excluded
        "statuesque figure",  # "statuesque" is excluded
    ],
)
def test_is_art_historical_query_returns_false(query):
    """Test that non-art-historical queries are correctly identified."""
    assert is_art_historical_query(query) is False


# =============================================================================
# Unit Tests: SearchParams.selected_embedding_model
# =============================================================================


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
    request = RequestFactory().get("/", {"model": model_param})
    params = SearchParams(request=request)
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
    request = RequestFactory().get("/", get_params)
    params = SearchParams(request=request)
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
def test_get_artworks_view_auto_resolves_to_jina_for_regular_query(mock_qdrant_service):
    """Test that search with model=auto uses Jina for non-art-historical queries."""
    client = Client()
    url = reverse("get-artworks") + "?query=cat&model=auto"

    with patch(
        "artsearch.src.services.search_service.get_total_works_for_filters",
        return_value=10,
    ):
        client.get(url)

    # Check that search_text was called with embedding_model="jina"
    mock_qdrant_service.search_text.assert_called_once()
    _, kwargs = mock_qdrant_service.search_text.call_args
    assert kwargs["embedding_model"] == "jina"


@pytest.mark.integration
@pytest.mark.django_db
def test_get_artworks_view_auto_resolves_to_clip_for_art_historical_query(mock_qdrant_service):
    """Test that search with model=auto uses CLIP for art-historical queries."""
    client = Client()
    url = reverse("get-artworks") + "?query=impressionism&model=auto"

    with patch(
        "artsearch.src.services.search_service.get_total_works_for_filters",
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
        "artsearch.src.services.search_service.get_total_works_for_filters",
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


# =============================================================================
# Integration Tests: Smart Auto Behavior in search_service
# =============================================================================


@pytest.mark.integration
@pytest.mark.django_db
def test_similarity_search_uses_jina_with_auto(mock_qdrant_service):
    """Test that similarity search uses Jina when model is auto."""
    from qdrant_client.models import ScoredPoint

    # Mock get_items_by_object_number to return an artwork (triggering similarity search)
    mock_item = MagicMock()
    mock_item.payload = {"museum": "smk", "object_number": "KMS1"}
    mock_qdrant_service.get_items_by_object_number.return_value = [mock_item]
    mock_qdrant_service.search_similar_images.return_value = []

    client = Client()
    url = reverse("get-artworks") + "?query=smk:KMS1&model=auto"

    with patch(
        "artsearch.src.services.search_service.get_total_works_for_filters",
        return_value=10,
    ):
        client.get(url)

    # Check that search_similar_images was called with embedding_model="jina"
    mock_qdrant_service.search_similar_images.assert_called_once()
    _, kwargs = mock_qdrant_service.search_similar_images.call_args
    assert kwargs["embedding_model"] == "jina"


# =============================================================================
# Unit Tests: SearchParams.selected_work_types with DEFAULT_WORK_TYPE_FILTER
# =============================================================================


@pytest.mark.unit
def test_search_params_selected_work_types_uses_default_when_no_url_param():
    """Test that selected_work_types uses DEFAULT_WORK_TYPE_FILTER when no work_types in URL."""
    with patch(
        "artsearch.views.context_builders.get_work_type_names",
        return_value=["painting", "drawing", "print"],
    ), patch(
        "artsearch.views.context_builders.DEFAULT_WORK_TYPE_FILTER",
        ["painting"],
    ):
        request = RequestFactory().get("/")
        params = SearchParams(request=request)
        assert params.selected_work_types == ["painting"]


@pytest.mark.unit
def test_search_params_selected_work_types_returns_all_when_default_is_none():
    """Test that selected_work_types returns all work types when DEFAULT_WORK_TYPE_FILTER is None."""
    with patch(
        "artsearch.views.context_builders.get_work_type_names",
        return_value=["painting", "drawing", "print"],
    ), patch(
        "artsearch.views.context_builders.DEFAULT_WORK_TYPE_FILTER",
        None,
    ):
        request = RequestFactory().get("/")
        params = SearchParams(request=request)
        assert params.selected_work_types == ["painting", "drawing", "print"]


@pytest.mark.unit
def test_search_params_selected_work_types_uses_url_param_when_present():
    """Test that URL work_types param overrides DEFAULT_WORK_TYPE_FILTER."""
    with patch(
        "artsearch.views.context_builders.get_work_type_names",
        return_value=["painting", "drawing", "print"],
    ), patch(
        "artsearch.views.context_builders.DEFAULT_WORK_TYPE_FILTER",
        ["painting"],
    ):
        request = RequestFactory().get("/", {"work_types": ["drawing", "print"]})
        params = SearchParams(request=request)
        assert params.selected_work_types == ["drawing", "print"]
