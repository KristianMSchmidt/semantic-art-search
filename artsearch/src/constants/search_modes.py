from typing import Literal

SearchMode = Literal["image", "title"]

VALID_SEARCH_MODES: frozenset[SearchMode] = frozenset(["image", "title"])

DEFAULT_SEARCH_MODE: SearchMode = "image"

SEARCH_MODE_TO_VECTOR_NAME = {
    "image": "image_jina",
    "title": "text_jina",
}


def validate_search_mode(mode: str) -> SearchMode:
    """Validate and return search mode, defaulting to 'image' for invalid values."""
    if mode in VALID_SEARCH_MODES:
        return mode  # type: ignore[return-value]
    return DEFAULT_SEARCH_MODE
