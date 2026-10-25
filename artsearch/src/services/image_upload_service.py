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
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

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


def embed_uploaded_image(data: bytes) -> tuple[str, list[float]]:
    """
    Embed an uploaded image (unless it is already cached) and return the key
    under which its vector is cached, along with the vector.
    """
    key = make_image_key(data)
    vector = get_uploaded_image_vector(key)
    if vector is None:
        vector = get_jina_embedder().generate_image_embedding(prepare_image(data))
        caches[CACHE_ALIAS].set(CACHE_KEY_PREFIX + key, vector, EMBEDDING_CACHE_SECONDS)
    return key, vector


def embed_upload(upload: UploadedFile | None) -> tuple[str, list[float]]:
    """
    Validate and embed an image upload from a request. Raises ImageUploadError
    with a user-facing message for bad uploads and when embedding fails.
    """
    if upload is None:
        raise ImageUploadError("No image received (multipart field 'image').")
    if upload.size is not None and upload.size > MAX_UPLOAD_BYTES:
        raise ImageUploadError(
            f"Image too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    data = upload.read()
    try:
        return embed_uploaded_image(data)
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
