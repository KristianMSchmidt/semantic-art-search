"""
Colourfulness scores for artwork thumbnails.

Scores are stored on ArtworkStats and used to show colourful artworks on the
default home page view (most of the collection is monochrome prints and
drawings).

Uses the spread term of the Hasler-Süsstrunk metric ("Measuring colourfulness
in natural images", 2003): the standard deviation of the image over two
opponent colour axes (red-green, yellow-blue). The metric's other term, the
mean colour, is left out: it rewards a uniform tint, so yellowed paper,
manuscripts and maps scored as colourful as chromolithographs. Without it,
greyscale scores 0, ink on toned paper ~5-15, and colourful paintings and
prints 20+.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import numpy as np
import requests
from PIL import Image

from etl.services.bucket_service import get_bucket_image_url

logger = logging.getLogger(__name__)

# Scoring a small copy is fast and gives nearly the same score
SCORE_MAX_DIMENSION = 128


def compute_colorfulness(image_bytes: bytes) -> float:
    """Colour spread of an image (0 for greyscale or a uniform tint)."""
    img = Image.open(BytesIO(image_bytes))
    img.thumbnail((SCORE_MAX_DIMENSION, SCORE_MAX_DIMENSION))
    rgb = np.asarray(img.convert("RGB"), dtype=np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = r - g
    yb = 0.5 * (r + g) - b
    return float(np.hypot(rg.std(), yb.std()))


def fetch_colorfulness(
    session: requests.Session, museum_slug: str, object_number: str
) -> float | None:
    """Download the app bucket thumbnail and score it; None on any failure."""
    url = get_bucket_image_url(museum_slug, object_number, use_etl_bucket=False)
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        return compute_colorfulness(response.content)
    except Exception as e:
        logger.warning(f"Could not score {museum_slug}:{object_number}: {e}")
        return None


def score_artworks(
    artworks: list[tuple[str, str]], workers: int
) -> list[float | None]:
    """Score (museum_slug, object_number) pairs in parallel, in input order."""
    with requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=workers)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(
                pool.map(lambda a: fetch_colorfulness(session, a[0], a[1]), artworks)
            )
