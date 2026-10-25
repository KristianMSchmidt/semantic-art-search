"""
Search by an uploaded image: validate and downscale it in memory, embed it with
Jina, and cache the vector so pagination and filter changes don't need the
image again. Uploads are never written to disk or storage.
"""

import base64
import hashlib
import io
import logging

from django.core.cache import caches
from django.utils import timezone
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

from artsearch.models import ImageSearchLog
from artsearch.src.services.jina_embedder import get_jina_embedder

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
# Jina tiles images larger than 512px into 512x512 chunks of 4,000 tokens each,
# so downscaling keeps an upload to a single tile
EMBED_IMAGE_SIZE = 512
# Images up to 40 megapixels decode fine; anything larger is refused rather
# than risking a decompression bomb
MAX_IMAGE_PIXELS = 40_000_000
EMBEDDING_CACHE_SECONDS = 60 * 60
# Site-wide cap on Jina image embeddings per UTC day (~4,000 tokens each), so
# uploads from many IPs can't drain the prepaid Jina balance that text search
# also depends on. Cached re-uploads don't count.
DAILY_EMBEDDING_CAP = 1000
CACHE_KEY_PREFIX = "uploaded-image-embedding:"
CACHE_ALIAS = "uploaded_images"


class ImageUploadError(Exception):
    """The upload is not an image we can search with; message is user-facing."""


def make_image_key(data: bytes) -> str:
    """Key identifying an upload, so the same image is only embedded once."""
    return hashlib.sha256(data).hexdigest()[:32]


def prepare_image(data: bytes) -> str:
    """
    Validate an uploaded image and return it as a base64 JPEG no larger than
    EMBED_IMAGE_SIZE on either side.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageUploadError(
            f"Image too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in ALLOWED_FORMATS:
            raise ImageUploadError("Please upload a JPEG, PNG, WebP or GIF image.")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ImageUploadError("Image dimensions are too large.")
        image.draft("RGB", (EMBED_IMAGE_SIZE, EMBED_IMAGE_SIZE))  # fast JPEG decode
        image = ImageOps.exif_transpose(image)  # phone photos store rotation in EXIF
        if image.mode in ("RGBA", "LA", "P"):
            # Transparent areas become white, as in the browser's downscaling
            rgba = image.convert("RGBA")
            image = Image.new("RGB", rgba.size, "white")
            image.paste(rgba, mask=rgba.getchannel("A"))
        else:
            image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageUploadError("Could not read the image. Please try another file.")

    image.thumbnail((EMBED_IMAGE_SIZE, EMBED_IMAGE_SIZE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


Source = ImageSearchLog.Source
Status = ImageSearchLog.Status
# Statuses that (may) have cost a Jina call: a call that errored or timed out
# can still have been billed
BILLED_STATUSES = [Status.EMBEDDED, Status.FAILED]


class DailyCapReached(ImageUploadError):
    """The site-wide daily embedding cap is used up."""


def embeddings_today() -> int:
    """Number of (possibly) billed Jina image embeddings since midnight UTC."""
    midnight = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return ImageSearchLog.objects.filter(
        status__in=BILLED_STATUSES, timestamp__gte=midnight
    ).count()


def _log(status: str, source: str) -> None:
    """Log an upload; a failed log write must not break the search itself."""
    try:
        ImageSearchLog.objects.create(status=status, source=source)
    except Exception:
        logger.exception("Could not write ImageSearchLog")


def _set_status(entry: ImageSearchLog, status: str) -> None:
    try:
        entry.status = status
        entry.save(update_fields=["status"])
    except Exception:
        logger.exception("Could not update ImageSearchLog")


def embed_uploaded_image(
    data: bytes, source: str = Source.WEB
) -> tuple[str, list[float]]:
    """
    Embed an uploaded image (unless it is already cached) and return the key
    under which its vector is cached, along with the vector. Every call is
    logged in ImageSearchLog.

    The log row is written before calling Jina and counted right after, so
    concurrent uploads can't all slip in under the daily cap.
    """
    key = make_image_key(data)
    vector = get_uploaded_image_vector(key)
    if vector is not None:
        _log(Status.CACHED, source)
        return key, vector

    # Reserve a slot; if the database is down this raises and nothing is embedded
    entry = ImageSearchLog.objects.create(status=Status.EMBEDDED, source=source)
    if embeddings_today() > DAILY_EMBEDDING_CAP:
        _set_status(entry, Status.DAILY_CAP)
        raise DailyCapReached(
            "Image search has reached its daily limit. Please try again tomorrow, "
            "or search with words instead."
        )
    try:
        image = prepare_image(data)
    except ImageUploadError:
        _set_status(entry, Status.REJECTED)
        raise
    try:
        vector = get_jina_embedder().generate_image_embedding(image)
    except Exception:
        _set_status(entry, Status.FAILED)
        raise
    caches[CACHE_ALIAS].set(CACHE_KEY_PREFIX + key, vector, EMBEDDING_CACHE_SECONDS)
    return key, vector


def embed_upload(
    upload: UploadedFile | None, source: str = Source.WEB
) -> tuple[str, list[float]]:
    """
    Validate and embed an image upload from a request. Raises ImageUploadError
    with a user-facing message for bad uploads and when embedding fails, and
    DailyCapReached when the daily cap is used up.
    """
    if upload is None:
        raise ImageUploadError("No image received (multipart field 'image').")
    if upload.size is not None and upload.size > MAX_UPLOAD_BYTES:
        _log(Status.REJECTED, source)
        raise ImageUploadError(
            f"Image too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    data = upload.read()
    try:
        return embed_uploaded_image(data, source)
    except ImageUploadError:
        raise
    except Exception as e:
        logger.exception("Embedding an uploaded image failed")
        raise ImageUploadError(
            "Something went wrong analysing the image. Please try again."
        ) from e


def get_uploaded_image_vector(key: str) -> list[float] | None:
    """Cached vector of an uploaded image, or None if unknown or expired."""
    return caches[CACHE_ALIAS].get(CACHE_KEY_PREFIX + key)
