"""
Tests for searching by an uploaded image (issue #101).

Jina and Qdrant are mocked; the image processing (Pillow) and the Django
cache holding the embeddings between requests are real.
"""

import base64
import io
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from PIL import Image

from artsearch.models import ImageSearchLog
from artsearch.src.services.image_upload_service import (
    CACHE_ALIAS,
    DAILY_EMBEDDING_CAP,
    DailyCapReached,
    EMBED_IMAGE_SIZE,
    ImageUploadError,
    embed_uploaded_image,
    embeddings_today,
    prepare_image,
)

FAKE_VECTOR = [0.1] * 256


def make_image_bytes(size=(1200, 800), image_format="PNG", mode="RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, color="red").save(buffer, format=image_format)
    return buffer.getvalue()


def make_upload(data: bytes | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "photo.png", data or make_image_bytes(), content_type="image/png"
    )


@pytest.fixture(autouse=True)
def clear_django_cache():
    caches[CACHE_ALIAS].clear()
    yield
    caches[CACHE_ALIAS].clear()


@pytest.fixture
def mock_jina():
    embedder = MagicMock()
    embedder.generate_image_embedding.return_value = FAKE_VECTOR
    with patch(
        "artsearch.src.services.image_upload_service.get_jina_embedder",
        return_value=embedder,
    ):
        yield embedder


@pytest.fixture
def mock_qdrant():
    service = MagicMock()
    service.search_image_vector.return_value = []
    with patch(
        "artsearch.src.services.search_service.QdrantService",
        return_value=service,
    ):
        yield service


# ---- Image processing ----


@pytest.mark.unit
def test_prepare_image_downscales_to_jpeg():
    encoded = prepare_image(make_image_bytes(size=(2000, 1000), mode="RGBA"))

    image = Image.open(io.BytesIO(base64.b64decode(encoded)))
    assert image.format == "JPEG"
    assert image.size == (EMBED_IMAGE_SIZE, EMBED_IMAGE_SIZE // 2)


@pytest.mark.unit
def test_prepare_image_applies_exif_rotation():
    # A landscape-stored photo marked "rotate 90°" (EXIF orientation 6), as phones save portraits
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    Image.new("RGB", (800, 400), "red").save(buffer, format="JPEG", exif=exif)

    image = Image.open(io.BytesIO(base64.b64decode(prepare_image(buffer.getvalue()))))

    assert image.width < image.height


@pytest.mark.unit
@pytest.mark.parametrize(
    "data",
    [
        b"not an image",
        make_image_bytes(size=(10, 10), image_format="BMP"),
    ],
)
def test_prepare_image_rejects_unsupported_files(data):
    with pytest.raises(ImageUploadError):
        prepare_image(data)


@pytest.mark.unit
@pytest.mark.django_db
def test_same_image_is_only_embedded_once(mock_jina):
    data = make_image_bytes()

    first_key, first_vector = embed_uploaded_image(data)
    second_key, second_vector = embed_uploaded_image(data)

    assert first_key == second_key
    assert first_vector == second_vector == FAKE_VECTOR
    assert mock_jina.generate_image_embedding.call_count == 1
    statuses = list(ImageSearchLog.objects.values_list("status", flat=True))
    assert sorted(statuses) == ["cached", "embedded"]


# ---- Daily cap and usage stats ----


@pytest.mark.unit
@pytest.mark.django_db
def test_daily_cap_refuses_new_embeddings_but_not_cached_images(mock_jina):
    cached_image = make_image_bytes(size=(100, 100))
    embed_uploaded_image(cached_image)
    ImageSearchLog.objects.bulk_create(
        ImageSearchLog(status=ImageSearchLog.Status.EMBEDDED, source="web")
        for _ in range(DAILY_EMBEDDING_CAP - 1)
    )
    mock_jina.generate_image_embedding.reset_mock()

    with pytest.raises(DailyCapReached):
        embed_uploaded_image(make_image_bytes(size=(200, 100)))
    # An image embedded earlier today is still served from the cache
    embed_uploaded_image(cached_image)

    mock_jina.generate_image_embedding.assert_not_called()
    assert ImageSearchLog.objects.filter(status="daily_cap").count() == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_failed_jina_calls_count_toward_cap_but_bad_files_dont(mock_jina):
    ImageSearchLog.objects.bulk_create(
        ImageSearchLog(status=ImageSearchLog.Status.FAILED, source="web")
        for _ in range(DAILY_EMBEDDING_CAP)
    )
    with pytest.raises(DailyCapReached):
        embed_uploaded_image(make_image_bytes())

    ImageSearchLog.objects.all().delete()
    with pytest.raises(ImageUploadError):
        embed_uploaded_image(b"not an image")
    assert ImageSearchLog.objects.get().status == "rejected"
    assert embeddings_today() == 0


@pytest.mark.integration
@pytest.mark.django_db
def test_upload_returns_429_when_daily_cap_reached(mock_jina):
    ImageSearchLog.objects.bulk_create(
        ImageSearchLog(status=ImageSearchLog.Status.EMBEDDED, source="web")
        for _ in range(DAILY_EMBEDDING_CAP)
    )

    response = Client().post("/artworks/image/", {"image": make_upload()})

    assert response.status_code == 429
    assert "daily limit" in response.json()["error"]


@pytest.mark.unit
@pytest.mark.django_db
def test_embeddings_from_previous_days_dont_count_toward_cap(mock_jina):
    ImageSearchLog.objects.bulk_create(
        ImageSearchLog(status=ImageSearchLog.Status.EMBEDDED, source="web")
        for _ in range(DAILY_EMBEDDING_CAP)
    )
    ImageSearchLog.objects.update(timestamp=timezone.now() - timedelta(days=1))

    embed_uploaded_image(make_image_bytes())

    mock_jina.generate_image_embedding.assert_called_once()


@pytest.mark.integration
@pytest.mark.django_db
def test_image_search_stats_command_shows_counts_per_day():
    ImageSearchLog.objects.create(status=ImageSearchLog.Status.EMBEDDED, source="web")
    ImageSearchLog.objects.create(status=ImageSearchLog.Status.EMBEDDED, source="api")
    ImageSearchLog.objects.create(status=ImageSearchLog.Status.CACHED, source="web")
    out = io.StringIO()

    call_command("image_search_stats", stdout=out)

    today_line = next(
        line for line in out.getvalue().splitlines()
        if line.startswith(timezone.now().date().isoformat())
    )
    # embedded, cached, daily_cap, rejected, failed, total
    assert today_line.split()[1:] == ["2", "1", "0", "0", "0", "3"]


# ---- Web flow: upload, then search with the key ----


@pytest.mark.integration
@pytest.mark.django_db
def test_upload_then_search_uses_image_vector_and_keeps_filters(mock_jina, mock_qdrant):
    client = Client()
    response = client.post("/artworks/image/", {"image": make_upload()})
    assert response.status_code == 200
    image_key = response.json()["image_key"]

    with patch(
        "artsearch.src.services.search_service.get_total_works_for_filters",
        return_value=100,
    ):
        response = client.get(
            "/artworks/",
            {"image": image_key, "query": "", "museums": "smk", "year_from": "1800"},
        )

    assert response.status_code == 200
    vector, search_args = mock_qdrant.search_image_vector.call_args.args
    assert vector == FAKE_VECTOR
    assert search_args.museum_prefilter == ["smk"]
    assert search_args.year_from == 1800
    # The next page keeps searching by the same image
    assert f"image={image_key}" in response.context["urls"]["get_artworks_with_params"]
    assert "Artworks resembling your image" in response.content.decode()


@pytest.mark.integration
@pytest.mark.django_db
def test_search_with_expired_image_key_asks_for_new_upload(mock_qdrant):
    response = Client().get("/artworks/", {"image": "unknown", "query": ""})

    assert response.status_code == 200
    assert "upload the image again" in response.content.decode()
    mock_qdrant.search_image_vector.assert_not_called()


@pytest.mark.integration
@pytest.mark.django_db
def test_upload_rejects_non_image(mock_jina):
    upload = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    response = Client().post("/artworks/image/", {"image": upload})

    assert response.status_code == 400
    assert "error" in response.json()
    mock_jina.generate_image_embedding.assert_not_called()


@pytest.mark.integration
def test_upload_requires_post():
    assert Client().get("/artworks/image/").status_code == 405


@pytest.mark.integration
def test_upload_rate_limited(mock_jina):
    with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
        response = Client().post("/artworks/image/", {"image": make_upload()})

    assert response.status_code == 429
    mock_jina.generate_image_embedding.assert_not_called()


@pytest.mark.integration
def test_upload_requires_csrf_token(mock_jina):
    client = Client(enforce_csrf_checks=True)
    response = client.post("/artworks/image/", {"image": make_upload()})

    assert response.status_code == 403


# ---- REST API ----


@pytest.mark.integration
@pytest.mark.django_db
def test_api_image_search_returns_results(mock_jina, mock_qdrant):
    mock_qdrant.search_image_vector.return_value = [{"title": "Red painting"}]

    response = Client().post(
        "/api/search/image/?limit=5&museums=smk", {"image": make_upload()}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"] == [{"title": "Red painting"}]
    assert data["limit"] == 5
    _, search_args = mock_qdrant.search_image_vector.call_args.args
    assert search_args.limit == 5
    assert search_args.museum_prefilter == ["smk"]


@pytest.mark.integration
@pytest.mark.django_db
def test_api_image_search_returns_json_error_when_embedding_fails(mock_jina):
    mock_jina.generate_image_embedding.side_effect = RuntimeError("Jina is down")

    response = Client().post("/api/search/image/", {"image": make_upload()})

    assert response.status_code == 400
    assert "error" in response.json()
    assert ImageSearchLog.objects.get().status == "failed"


@pytest.mark.integration
def test_api_image_search_requires_image():
    response = Client().post("/api/search/image/")

    assert response.status_code == 400
