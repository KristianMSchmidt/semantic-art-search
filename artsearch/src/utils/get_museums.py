from artsearch.src.constants import SUPPORTED_MUSEUMS


def get_museum_names() -> list[str]:
    """
    Get a list of supported museum slugs.
    """
    return [museum["slug"] for museum in SUPPORTED_MUSEUMS]
