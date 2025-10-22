from artsearch.src.constants.museums import SUPPORTED_MUSEUMS


def get_museum_slugs() -> list[str]:
    """
    Get a list of supported museum slugs.
    """
    return [museum["slug"] for museum in SUPPORTED_MUSEUMS]


def get_museum_full_name(museum_slug: str) -> str:
    """
    Get full museum name from slug.
    """
    for museum in SUPPORTED_MUSEUMS:
        if museum["slug"] == museum_slug.lower():
            return museum["full_name"]
    return museum_slug
