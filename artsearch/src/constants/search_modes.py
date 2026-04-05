from typing import Literal

SearchMode = Literal["auto", "image", "title"]

VALID_SEARCH_MODES: frozenset[SearchMode] = frozenset(["auto", "image", "title"])

SEARCH_MODES = [
    {
        "value": "auto",
        "label": "Auto",
        "description": "Combines visual and title search",
    },
    {"value": "image", "label": "Visual", "description": "Search by visual appearance"},
    {
        "value": "title",
        "label": "By title",
        "description": "Search by title similarity",
    },
]

DEFAULT_SEARCH_MODE: SearchMode = "auto"

SEARCH_MODE_TO_VECTOR_NAME = {
    "image": "image_jina",
    "title": "text_jina",
}


def validate_search_mode(mode: str) -> SearchMode:
    """Validate and return search mode, defaulting to 'auto' for invalid values."""
    if mode in VALID_SEARCH_MODES:
        return mode  # type: ignore[return-value]
    return DEFAULT_SEARCH_MODE
