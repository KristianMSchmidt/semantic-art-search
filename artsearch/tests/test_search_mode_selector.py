"""
Tests for search mode selector functionality.

Tests the ability to choose between image and title search modes,
and the auto hybrid mode using Qdrant RRF fusion.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client, RequestFactory
from django.urls import reverse

from artsearch.src.constants.search_modes import (
    SEARCH_MODES,
    validate_search_mode,
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
# Unit Tests: validate_search_mode()
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "model_param,expected",
    [
        ("auto", "auto"),
        ("image", "image"),
        ("title", "title"),
    ],
)
def test_validate_search_mode_valid_values(model_param, expected):
    """Test that valid search mode choices are returned as-is."""
    assert validate_search_mode(model_param) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "model_param",
    ["clip", "jina", "invalid", "", "AUTO"],
)
def test_validate_search_mode_invalid_defaults_to_auto(model_param):
    """Test that invalid values default to 'auto'."""
    assert validate_search_mode(model_param) == "auto"


# =============================================================================
# Unit Tests: SearchParams.selected_search_mode
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "model_param,expected",
    [
        ("auto", "auto"),
        ("image", "image"),
        ("title", "title"),
    ],
)
def test_search_params_selected_search_mode_valid_values(model_param, expected):
    """Test that SearchParams correctly extracts valid search mode values from query params."""
    request = RequestFactory().get("/", {"model": model_param})
    params = SearchParams(request=request)
    assert params.selected_search_mode == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "get_params,expected",
    [
        ({"model": "clip"}, "auto"),   # Old value defaults to auto
        ({"model": "jina"}, "auto"),   # Old value defaults to auto
        ({"model": "invalid"}, "auto"),
        ({}, "auto"),
    ],
)
def test_search_params_selected_search_mode_invalid_defaults_to_auto(
    get_params, expected
):
    """Test that invalid or missing search mode param defaults to 'auto'."""
    request = RequestFactory().get("/", get_params)
    params = SearchParams(request=request)
    assert params.selected_search_mode == expected


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
        ("image", "model=image"),
        ("title", "model=title"),
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
def test_home_view_includes_search_modes_in_context(mock_qdrant_service):
    """Test that home view includes search modes in context."""
    client = Client()
    url = reverse("home")

    response = client.get(url)

    assert response.status_code == 200
    assert "search_modes" in response.context
    assert response.context["search_modes"] == SEARCH_MODES
    assert "selected_model" in response.context
    assert response.context["selected_model"] == "auto"


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_param,expected",
    [
        ("image", "image"),
        ("title", "title"),
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
def test_get_artworks_view_auto_passes_auto_to_qdrant(mock_qdrant_service):
    """Test that search with model=auto passes 'auto' to QdrantService.search_text."""
    client = Client()
    url = reverse("get-artworks") + "?query=cat&model=auto"

    with patch(
        "artsearch.src.services.search_service.get_total_works_for_filters",
        return_value=10,
    ):
        client.get(url)

    mock_qdrant_service.search_text.assert_called_once()
    _, kwargs = mock_qdrant_service.search_text.call_args
    assert kwargs["embedding_model"] == "auto"


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize("model", ["image", "title"])
def test_get_artworks_view_passes_explicit_mode_to_search(mock_qdrant_service, model):
    """Test that explicit mode is passed through to QdrantService.search_text."""
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
        ("image", "image_jina"),
        ("title", "text_jina"),
    ],
)
def test_qdrant_service_search_text_uses_correct_vector_name(
    model, expected_vector_name
):
    """Test that QdrantService uses the correct vector name for image and title modes."""
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

    with patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina:
        mock_embedder = MagicMock()
        mock_embedder.generate_text_embedding.return_value = [0.1] * 256
        mock_jina.return_value = mock_embedder

        service.search_text(search_args, embedding_model=model)

    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs["using"] == expected_vector_name


@pytest.mark.unit
def test_qdrant_service_search_text_auto_uses_prefetch_rrf():
    """Test that auto mode uses prefetch + RRF fusion, not a single vector search."""
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

    with patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina:
        mock_embedder = MagicMock()
        mock_embedder.generate_text_embedding.return_value = [0.1] * 256
        mock_jina.return_value = mock_embedder

        service.search_text(search_args, embedding_model="auto")

    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    # Auto mode uses prefetch, not a single 'using' parameter
    assert "prefetch" in kwargs
    assert len(kwargs["prefetch"]) == 2
    assert kwargs["prefetch"][0].using == "image_jina"
    assert kwargs["prefetch"][1].using == "text_jina"
    assert "using" not in kwargs


@pytest.mark.unit
def test_qdrant_service_search_text_auto_passes_filter_into_prefetch():
    """Test that auto mode applies filters inside each prefetch block, not just at the top level."""
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
        work_type_prefilter=["painting"],
        museum_prefilter=["smk", "met"],
    )

    with patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina:
        mock_embedder = MagicMock()
        mock_embedder.generate_text_embedding.return_value = [0.1] * 256
        mock_jina.return_value = mock_embedder

        service.search_text(search_args, embedding_model="auto")

    _, kwargs = mock_client.query_points.call_args
    prefetch = kwargs["prefetch"]
    assert len(prefetch) == 2
    # Both prefetch blocks must carry the filter so candidates are pre-filtered
    assert prefetch[0].filter is not None, "image_jina prefetch must have a filter"
    assert prefetch[1].filter is not None, "text_jina prefetch must have a filter"
    # The same filter object should be used for both
    assert prefetch[0].filter == prefetch[1].filter


@pytest.mark.unit
def test_qdrant_service_search_similar_images_uses_image_jina():
    """Test that search_similar_images always uses image_jina vector."""
    from artsearch.src.services.qdrant_service import (
        QdrantService,
        SearchFunctionArguments,
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.points = []
    mock_client.query_points.return_value = mock_response

    # Mock the target artwork vector lookup
    mock_item = MagicMock()
    mock_item.vector = {"image_jina": [0.1] * 256, "image_clip": [0.0] * 768}

    service = QdrantService(collection_name="test", qdrant_client=mock_client)

    with patch.object(service, "get_items_by_object_number", return_value=[mock_item]):
        search_args = SearchFunctionArguments(
            query="KMS1",
            limit=10,
            offset=0,
            work_type_prefilter=None,
            museum_prefilter=None,
            object_number="KMS1",
            object_museum="smk",
        )
        service.search_similar_images(search_args)

    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs["using"] == "image_jina"


# =============================================================================
# Integration Tests: Similarity search in search_service
# =============================================================================


@pytest.mark.integration
@pytest.mark.django_db
def test_similarity_search_calls_search_similar_images(mock_qdrant_service):
    """Test that a similarity search query calls search_similar_images (not search_text)."""
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

    mock_qdrant_service.search_similar_images.assert_called_once()
    mock_qdrant_service.search_text.assert_not_called()


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
