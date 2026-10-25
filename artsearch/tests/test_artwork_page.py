"""
Integration tests for the shareable artwork page, sitemap and robots.txt.

Qdrant is mocked; PostgreSQL (descriptions, ArtworkStats) is real.
"""

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from qdrant_client import models

from artsearch.models import ArtworkDescription, ArtworkStats
from artsearch.sitemaps import artwork_page_path
from etl.services.bucket_service import get_bucket_image_url


def _payload(museum: str, object_number: str, title: str) -> dict:
    return {
        "museum": museum,
        "object_number": object_number,
        "museum_db_id": f"db-{object_number}",
        "title": title,
        "artists": ["Vilhelm Hammershøi"],
        "production_date": "1904",
        "work_types": ["painting"],
        "searchable_work_types": ["painting"],
    }


QUERY_PAYLOAD = _payload("smk", "KKS10208/5", "Interior with a Young Woman")


def _similar_result(museum: str, object_number: str, title: str, is_query: bool) -> dict:
    return {
        "title": title,
        "artist": "Vilhelm Hammershøi",
        "thumbnail_url": f"https://example.com/{museum}_{object_number}.jpg",
        "museum_slug": museum,
        "object_number": object_number,
        "is_query_artwork": is_query,
    }


@pytest.fixture
def mock_qdrant():
    """QdrantService that knows one artwork (QUERY_PAYLOAD) and returns two similar ones."""
    with patch("artsearch.views.views.QdrantService") as service_cls:
        service = service_cls.return_value

        def get_items(object_number, object_museum=None, **kwargs):
            if (object_museum, object_number) == ("smk", "KKS10208/5"):
                return [models.ScoredPoint(id=1, version=1, score=1.0, payload=QUERY_PAYLOAD)]
            return []

        service.get_items_by_object_number.side_effect = get_items
        service.search_similar_images.return_value = [
            _similar_result("smk", "KKS10208/5", "Interior with a Young Woman", True),
            _similar_result("met", "Burdick 218, N220.35", "Quiet Room", False),
            _similar_result("rma", "SK-A-1505", "Sunlit Interior", False),
        ]
        yield service


@pytest.mark.integration
@pytest.mark.django_db
def test_artwork_page_renders_artwork_with_share_tags_and_similar(mock_qdrant):
    url = reverse("artwork-page", args=["smk", "KKS10208/5"])
    assert url == "/artwork/smk/KKS10208/5/"  # slash in object number stays readable

    response = Client().get(url)

    assert response.status_code == 200
    html = response.content.decode()
    assert "<title>Interior with a Young Woman – Vilhelm Hammershøi | Semantic Art Search</title>" in html
    image_url = get_bucket_image_url("smk", "KKS10208/5", use_etl_bucket=False)
    assert f'<meta property="og:image" content="{image_url}" />' in html
    assert '<link rel="canonical" href="http://testserver/artwork/smk/KKS10208/5/">' in html
    assert 'title="Share a link to this artwork"' in html
    # Similar artworks link to their own pages; the artwork itself is left out
    assert 'href="/artwork/met/Burdick%20218,%20N220.35/"' in html
    assert 'href="/artwork/rma/SK-A-1505/"' in html
    assert 'href="/artwork/smk/KKS10208/5/"' not in html


@pytest.mark.integration
@pytest.mark.django_db
def test_artwork_page_shows_cached_description_without_generating(mock_qdrant):
    ArtworkDescription.objects.create(
        museum_slug="smk", object_number="KKS10208/5", description="A quiet interior."
    )

    with patch("artsearch.views.views.generate_description") as generate:
        response = Client().get("/artwork/smk/KKS10208/5/")

    html = response.content.decode()
    assert "A quiet interior." in html
    assert '<meta name="description" content="A quiet interior.">' in html
    generate.assert_not_called()


@pytest.mark.integration
@pytest.mark.django_db
def test_artwork_page_without_cached_description_offers_button_only(mock_qdrant):
    with patch("artsearch.views.views.generate_description") as generate:
        response = Client().get("/artwork/smk/KKS10208/5/")

    html = response.content.decode()
    assert "Tell me about this artwork" in html
    assert "object_number=KKS10208%2F5" in html  # button requests the right artwork
    generate.assert_not_called()  # crawlers must not trigger OpenAI calls


@pytest.mark.integration
@pytest.mark.django_db
def test_artwork_page_still_renders_when_similar_search_fails(mock_qdrant):
    mock_qdrant.search_similar_images.side_effect = ValueError("no vector")

    response = Client().get("/artwork/smk/KKS10208/5/")

    assert response.status_code == 200
    assert "Similar artworks</h2>" not in response.content.decode()


@pytest.mark.integration
@pytest.mark.django_db
def test_show_more_loads_next_similar_artworks_on_the_page(mock_qdrant):
    # First batch: the artwork itself plus 12 others fills the page
    mock_qdrant.search_similar_images.return_value = [
        _similar_result("smk", "KKS10208/5", "Itself", True)
    ] + [_similar_result("cma", f"1915.{i}", f"Work {i}", False) for i in range(12)]

    html = Client().get("/artwork/smk/KKS10208/5/").content.decode()

    # 13 results consumed (itself + 12), so the next batch starts at 13
    assert 'hx-get="/artwork/smk/KKS10208/5/similar/?offset=13"' in html

    mock_qdrant.search_similar_images.return_value = [
        _similar_result("cma", "1915.99", "Last Work", False)
    ]
    response = Client().get("/artwork/smk/KKS10208/5/similar/?offset=13")

    assert response.status_code == 200
    fragment = response.content.decode()
    assert 'href="/artwork/cma/1915.99/"' in fragment
    assert "Show more" not in fragment  # fewer than a full batch: nothing left
    assert mock_qdrant.search_similar_images.call_args.args[0].offset == 13


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/artwork/smk/NOPE/","/artwork/unknown-museum/KKS10208/5/"])
def test_artwork_page_404_for_unknown_artwork(mock_qdrant, url):
    response = Client().get(url)

    assert response.status_code == 404


@pytest.mark.unit
@pytest.mark.parametrize(
    "museum, object_number",
    [
        ("smk", "KMS1"),
        ("smk", "KKS10208/5"),
        ("smk", "KKSgb6915 verso"),
        ("met", "Burdick 218, N220.35"),
        ("met", "52.586.1(4)"),
        ("aic", "Obj: 274417"),
        ("rma", "RP-T-1963-118(V)"),
        ("met", "a&b*c–d"),
    ],
)
def test_artwork_page_path_matches_reverse(museum, object_number):
    """The sitemap's fast path builder must produce exactly the URLs Django routes."""
    assert artwork_page_path(museum, object_number) == reverse(
        "artwork-page", args=[museum, object_number]
    )


@pytest.mark.integration
@pytest.mark.django_db
def test_sitemap_lists_artwork_pages():
    ArtworkStats.objects.create(
        museum_slug="smk", object_number="KKS10208/5", searchable_work_types=["drawing"]
    )
    ArtworkStats.objects.create(
        museum_slug="met", object_number="Burdick 218, N220.35", searchable_work_types=["print"]
    )
    client = Client()

    index = client.get("/sitemap.xml")
    assert index.status_code == 200
    assert "/sitemap-artworks.xml" in index.content.decode()

    sitemap = client.get("/sitemap-artworks.xml").content.decode()
    assert "<loc>http://testserver/artwork/smk/KKS10208/5/</loc>" in sitemap
    assert "<loc>http://testserver/artwork/met/Burdick%20218,%20N220.35/</loc>" in sitemap


@pytest.mark.integration
def test_robots_txt_points_to_sitemap_and_blocks_search_endpoints():
    response = Client().get("/robots.txt")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "Sitemap: http://testserver/sitemap.xml" in body
    assert "Disallow: /artworks/" in body  # HTMX search endpoint (Jina API cost)
    assert "Disallow: /api/" in body
    assert "Disallow: /artwork/*/similar/" in body  # HTMX fragment, not a page


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/artwork/unknown-museum/KKS10208/5/similar/",
        "/artwork/smk/KKS10208/5/similar/?offset=100000",  # past the deep-offset cap
    ],
)
def test_show_more_returns_nothing_for_invalid_requests(mock_qdrant, url):
    response = Client().get(url)

    assert response.status_code == 200
    assert "/artwork/" not in response.content.decode()
    mock_qdrant.search_similar_images.assert_not_called()
