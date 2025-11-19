"""Cache operations for artwork descriptions."""

from typing import Optional
from artsearch.models import ArtworkDescription


def get_cached_description(museum_slug: str, object_number: str) -> Optional[str]:
    """Retrieve cached artwork description from database.

    Args:
        museum_slug: Museum identifier (e.g., 'smk', 'met')
        object_number: Artwork object number

    Returns:
        Cached description if found, None otherwise
    """
    try:
        cached = ArtworkDescription.objects.get(
            museum_slug=museum_slug, object_number=object_number
        )
        return cached.description
    except ArtworkDescription.DoesNotExist:
        return None


def save_to_cache(museum_slug: str, object_number: str, description: str) -> None:
    """Save generated description to cache.

    Args:
        museum_slug: Museum identifier (e.g., 'smk', 'met')
        object_number: Artwork object number
        description: Generated description text
    """
    ArtworkDescription.objects.update_or_create(
        museum_slug=museum_slug,
        object_number=object_number,
        defaults={"description": description},
    )
