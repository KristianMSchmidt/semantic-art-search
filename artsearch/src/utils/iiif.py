"""
IIIF Image API URLs for museums that serve their images through IIIF.

The ETL stores a full-resolution `image_url` per artwork in TransformedData.
For IIIF museums, that URL is built on the museum's IIIF image service, so the
service URL (and from it info.json and sized images) can be derived from it.
CMA and MET have no IIIF image service and are not listed. AIC has one
(https://www.artic.edu/iiif/2/<image_id>), but it sits behind a Cloudflare bot
challenge that blocked every request from a fresh browser in testing (Oct 2026),
so it's left out until that changes.
"""

import re

from etl.models import TransformedData

# Stored image_url formats per museum (see the extract_image_url() methods of
# the ETL transformers). The first group is the IIIF image service URL.
IIIF_IMAGE_URL_PATTERNS = {
    # SMK stores the bare service URL (raw image_iiif_id), not an image
    "smk": re.compile(r"^(https://iip\.smk\.dk/iiif/jp2/[^/]+)$"),
    "nga": re.compile(
        r"^(https://api\.nga\.gov/iiif/[^/]+)/full/full/0/default\.jpg$"
    ),
    # IIIF Image API v3 (micr.io), hence "max" instead of "full"
    "rma": re.compile(r"^(https://iiif\.micr\.io/[^/]+)/full/max/0/default\.jpg$"),
}


def get_iiif_service_url(museum_slug: str, image_url: str | None) -> str | None:
    """
    Get the IIIF image service URL for an artwork's stored image_url.

    Returns None for museums without IIIF, missing image URLs and URLs that
    don't have the expected format.
    """
    pattern = IIIF_IMAGE_URL_PATTERNS.get(museum_slug)
    if pattern is None or not image_url:
        return None
    match = pattern.match(image_url)
    return match.group(1) if match else None


def get_artwork_iiif_service_url(museum_slug: str, object_number: str) -> str | None:
    """Look up an artwork's IIIF image service URL from its TransformedData row."""
    if museum_slug not in IIIF_IMAGE_URL_PATTERNS:
        return None  # no IIIF for this museum, so skip the query
    image_url = (
        TransformedData.objects.filter(
            museum_slug=museum_slug, object_number=object_number
        )
        .values_list("image_url", flat=True)
        .first()
    )
    return get_iiif_service_url(museum_slug, image_url)


def get_iiif_info_url(service_url: str) -> str:
    """URL of the image's info.json, which deep zoom viewers load."""
    return f"{service_url}/info.json"


def get_iiif_sized_image_url(service_url: str, max_size: int) -> str:
    """
    URL of the whole image scaled to fit within max_size x max_size.

    The "!w,h" size syntax is valid in both IIIF Image API v2 and v3.
    """
    return f"{service_url}/full/!{max_size},{max_size}/0/default.jpg"
