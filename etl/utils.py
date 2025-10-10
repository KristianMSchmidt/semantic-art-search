"""
Utility functions for ETL pipeline.
"""

import uuid


def generate_uuid5(museum_slug: str, object_number: str) -> str:
    """
    Generate a deterministic UUID5 from museum slug and object number.

    This ensures the same artwork always gets the same Qdrant point ID,
    which is critical for:
    - Upsert operations (updating existing points instead of creating duplicates)
    - Cross-environment consistency (same ID in dev and prod)
    - Database migrations (ID doesn't change if PostgreSQL is reset)

    Args:
        museum_slug: Museum identifier (e.g., "smk", "cma", "met", "rma")
        object_number: Artwork's unique identifier within the museum

    Returns:
        UUID5 string that uniquely identifies this artwork

    Examples:
        >>> generate_uuid5("smk", "KMS1")
        'a1b2c3d4-e5f6-5a7b-8c9d-0e1f2a3b4c5d'
        >>> generate_uuid5("smk", "KMS1")  # Same inputs = same output
        'a1b2c3d4-e5f6-5a7b-8c9d-0e1f2a3b4c5d'
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{museum_slug}-{object_number}"))
