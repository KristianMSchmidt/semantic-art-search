"""
Tests for the production year filter.

The same overlap rules are implemented twice: in PostgreSQL (browse mode and
total counts, via ArtworkStats) and in Qdrant (text and similarity search).
Both are run against the same artworks so they can't drift apart.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from django.urls import reverse
from qdrant_client import QdrantClient, models

from artsearch.models import ArtworkStats
from artsearch.src.constants.museums import CENTURY_SLUGS, get_century_index
from artsearch.src.services.browse_service import get_random_artwork_ids
from artsearch.src.services.museum_stats_service import get_total_works_for_filters
from artsearch.src.services.qdrant_service import (
    QdrantService,
    SearchFunctionArguments,
)
from artsearch.src.services.search_service import parse_year_range


# (object_number, production_date_start, production_date_end)
ARTWORKS = [
    ("A", 1600, 1650),
    ("B", 1690, 1720),  # spans the turn of the century
    ("C", 1750, None),  # start only
    ("D", None, 1610),  # end only
    ("E", None, None),  # undated
]

YEAR_RANGE_CASES = [
    # (year_from, year_to, expected object numbers)
    (None, None, {"A", "B", "C", "D", "E"}),
    (1640, 1700, {"A", "B"}),
    (1700, None, {"B", "C"}),
    (None, 1620, {"A", "D"}),
    (1750, 1750, {"C"}),
    (1800, 1900, set()),
]


# =============================================================================
# Unit Tests: parse_year_range()
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw_from,raw_to,expected",
    [
        (None, None, (None, None)),
        ("", "", (None, None)),
        ("1600", "1700", (1600, 1700)),
        (" 1600 ", None, (1600, None)),
        ("1700", "1600", (1600, 1700)),  # reversed range is swapped
        ("-500", "100", (-500, 100)),
        ("abc", "1700", (None, 1700)),
        ("1600.5", "1700", (None, 1700)),
        ("99999999999", "1700", (None, 1700)),  # out of range
    ],
)
def test_parse_year_range(raw_from, raw_to, expected):
    assert parse_year_range(raw_from, raw_to) == expected


# =============================================================================
# Integration Tests: PostgreSQL (browse mode and total counts)
# =============================================================================


@pytest.fixture
def artwork_stats():
    ArtworkStats.objects.bulk_create(
        ArtworkStats(
            museum_slug="smk",
            object_number=object_number,
            searchable_work_types=["painting"],
            production_date_start=start,
            production_date_end=end,
        )
        for object_number, start, end in ARTWORKS
    )


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize("year_from,year_to,expected", YEAR_RANGE_CASES)
def test_browse_filters_by_year_range(artwork_stats, year_from, year_to, expected):
    ids = get_random_artwork_ids(
        museums=None,
        work_types=None,
        seed="seed",
        limit=10,
        offset=0,
        year_from=year_from,
        year_to=year_to,
    )

    assert {object_number for _, object_number in ids} == expected


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize("year_from,year_to,expected", YEAR_RANGE_CASES)
def test_total_works_counts_year_range(artwork_stats, year_from, year_to, expected):
    total = get_total_works_for_filters(("smk",), ("painting",), year_from, year_to)

    assert total == len(expected)


# =============================================================================
# Integration Tests: Qdrant (in-memory client, real filter evaluation)
# =============================================================================


@pytest.fixture
def qdrant_service():
    client = QdrantClient(":memory:")
    client.create_collection(
        "test",
        vectors_config={
            "image_jina": models.VectorParams(size=2, distance=models.Distance.COSINE)
        },
    )
    client.upsert(
        "test",
        points=[
            models.PointStruct(
                id=i,
                vector={"image_jina": [1.0, 0.5]},
                payload={
                    "museum": "smk",
                    "object_number": object_number,
                    "searchable_work_types": ["painting"],
                    "production_date_start": start,
                    "production_date_end": end,
                },
            )
            for i, (object_number, start, end) in enumerate(ARTWORKS)
        ],
    )
    return QdrantService(collection_name="test", qdrant_client=client)


@pytest.mark.integration
@pytest.mark.parametrize("year_from,year_to,expected", YEAR_RANGE_CASES)
def test_text_search_filters_by_year_range(
    qdrant_service, year_from, year_to, expected
):
    search_args = SearchFunctionArguments(
        query="landscape",
        limit=10,
        offset=0,
        work_type_prefilter=None,
        museum_prefilter=None,
        year_from=year_from,
        year_to=year_to,
    )

    with patch(
        "artsearch.src.services.qdrant_service.get_jina_embedder"
    ) as mock_jina, patch(
        "artsearch.src.services.qdrant_service.format_hits",
        side_effect=lambda points: [p.payload for p in points],
    ):
        mock_jina.return_value.generate_text_embedding.return_value = [1.0, 0.5]
        results = qdrant_service.search_text(search_args)

    assert {r["object_number"] for r in results} == expected


@pytest.mark.integration
def test_similarity_search_keeps_query_artwork_outside_year_range(qdrant_service):
    """The artwork a similarity search starts from is shown even if undated."""
    query_filter = qdrant_service._build_filter(
        work_types=None,
        museums=None,
        object_number="E",
        year_from=1640,
        year_to=1700,
    )

    points, _ = qdrant_service.qdrant_client.scroll("test", scroll_filter=query_filter)

    assert {p.payload["object_number"] for p in points} == {"A", "B", "E"}


# =============================================================================
# Integration Tests: Views and API
# =============================================================================


@pytest.fixture
def mock_search_qdrant():
    mock_service = MagicMock()
    mock_service.search_text.return_value = []
    mock_service.get_items_by_object_number.return_value = []
    with patch(
        "artsearch.src.services.search_service.QdrantService",
        return_value=mock_service,
    ), patch(
        "artsearch.src.services.search_service.get_total_works_for_filters",
        return_value=10,
    ) as mock_total:
        yield mock_service, mock_total


@pytest.mark.integration
@pytest.mark.django_db
def test_search_view_applies_year_range_and_keeps_it_in_url(mock_search_qdrant):
    mock_service, mock_total = mock_search_qdrant
    client = Client()

    response = client.get(
        reverse("get-artworks"),
        {"query": "storm at sea", "model": "image", "year_from": "1700", "year_to": "1600"},
    )

    search_args = mock_service.search_text.call_args.args[0]
    assert (search_args.year_from, search_args.year_to) == (1600, 1700)
    assert mock_total.call_args.args[2:] == (1600, 1700)
    assert response["HX-Replace-Url"] == (
        reverse("home") + "?query=storm+at+sea&year_from=1600&year_to=1700&model=image"
    )
    # Infinite scroll keeps the year range
    assert "year_from=1600&year_to=1700" in response.context["urls"]["get_artworks_with_params"]


@pytest.mark.integration
@pytest.mark.django_db
def test_search_view_ignores_blank_year_inputs(mock_search_qdrant):
    """Empty From/To inputs are submitted as blank values and mean no bound."""
    mock_service, _ = mock_search_qdrant
    client = Client()

    response = client.get(
        reverse("get-artworks"),
        {"query": "sunset", "model": "image", "year_from": "", "year_to": ""},
    )

    search_args = mock_service.search_text.call_args.args[0]
    assert (search_args.year_from, search_args.year_to) == (None, None)
    assert "year_" not in response["HX-Replace-Url"]


@pytest.mark.integration
@pytest.mark.django_db
def test_home_view_restores_year_range_from_url():
    client = Client()

    response = client.get(reverse("home") + "?year_from=1600&year_to=1700")

    assert "yearRange('1600', '1700')" in response.content.decode()


@pytest.mark.integration
def test_api_search_passes_year_range():
    with patch(
        "artsearch.api.views.handle_search",
        return_value={"results": [], "total_works": 0, "error_message": None},
    ) as mock_handle_search:
        response = Client().get("/api/search/?query=landscape&year_from=1800&year_to=1899")

    assert response.status_code == 200
    _, kwargs = mock_handle_search.call_args
    assert (kwargs["year_from"], kwargs["year_to"]) == (1800, 1899)


@pytest.mark.unit
@pytest.mark.parametrize(
    "start, end, expected",
    [
        (-4800, None, "before-1400"),
        (1399, 1410, "before-1400"),
        (1400, None, "1400s"),
        (1650, 1700, "1600s"),
        (1899, None, "1800s"),
        (1900, None, "from-1900"),
        (2021, None, "from-1900"),
        (None, 1650, "1600s"),  # no start year: use the end year
        (None, None, "undated"),
    ],
)
def test_get_century_index(start, end, expected):
    """
    Art map century groups: by start year, clamped at both ends.

    Potential bugs this could catch:
    - Off-by-one at century boundaries
    - Ancient or modern years falling outside the groups
    - Artworks with only an end year counted as undated
    """
    assert CENTURY_SLUGS[get_century_index(start, end)] == expected
