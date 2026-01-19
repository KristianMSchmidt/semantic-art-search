import re
from typing import Literal

EmbeddingModelChoice = Literal["auto", "clip", "jina"]
ResolvedEmbeddingModel = Literal["clip", "jina"]

VALID_MODELS: frozenset[EmbeddingModelChoice] = frozenset(["auto", "clip", "jina"])

EMBEDDING_MODELS = [
    {"value": "auto", "label": "Auto", "description": "Smart selection based on query"},
    {"value": "clip", "label": "OpenAI CLIP", "description": "OpenAI CLIP ViT-L/14"},
    {"value": "jina", "label": "Jina CLIP v2", "description": "Jina CLIP v2"},
]

DEFAULT_EMBEDDING_MODEL: EmbeddingModelChoice = "auto"


def validate_embedding_model(model: str) -> EmbeddingModelChoice:
    """Validate and return model, defaulting to 'auto' for invalid values."""
    if model in VALID_MODELS:
        return model  # type: ignore[return-value]
    return DEFAULT_EMBEDDING_MODEL


# Comprehensive list of art movements and styles for query detection
ART_MOVEMENTS: frozenset[str] = frozenset([
    # Classical & Medieval
    "gothic", "romanesque", "byzantine", "medieval",
    # Renaissance & Early Modern
    "renaissance", "mannerism", "baroque", "rococo", "neoclassicism", "neo-classicism",
    # 19th Century
    "romanticism", "realism", "naturalism", "impressionism", "post-impressionism",
    "pointillism", "divisionism", "luminism", "tonalism", "symbolism",
    "pre-raphaelite", "arts and crafts", "aestheticism",
    # Early 20th Century
    "art nouveau", "art deco", "jugendstil", "secession", "vienna secession",
    "fauvism", "expressionism", "cubism", "futurism", "orphism", "vorticism",
    "dadaism", "dada", "surrealism", "constructivism", "suprematism",
    "de stijl", "bauhaus", "precisionism", "new objectivity",
    # Mid-20th Century
    "abstract expressionism", "action painting", "color field",
    "pop art", "op art", "kinetic art", "hard-edge painting",
    "minimalism", "post-minimalism", "conceptual art", "fluxus",
    "photorealism", "hyperrealism",
    # Late 20th Century & Contemporary
    "neo-expressionism", "neo-geo", "postmodernism", "deconstructivism",
    "installation art", "land art", "performance art",
    "street art", "graffiti art", "lowbrow", "outsider art",
    # Regional/Cultural
    "ukiyo-e", "japonisme", "chinoiserie", "orientalism",
    "mexican muralism", "harlem renaissance",
    "socialist realism", "magic realism",
])

# Common non-art words ending in -esque to exclude
_NON_ART_ESQUE_WORDS: frozenset[str] = frozenset([
    "picturesque", "grotesque", "burlesque", "statuesque", "romanesque",
])


def is_art_historical_query(query: str) -> bool:
    """
    Detect if a query is art-historical based on keywords and style patterns.

    Returns True if the query contains:
    - Art movement keywords (case-insensitive)
    - Style patterns like "in the style of", "*istic", "*esque"
    """
    query_lower = query.lower()

    # Check for art movement keywords
    for movement in ART_MOVEMENTS:
        # Use word boundary matching to avoid partial matches
        # e.g., "realistic" shouldn't match "realism"
        pattern = r'\b' + re.escape(movement) + r'\b'
        if re.search(pattern, query_lower):
            return True

    # Check for "in the style of" pattern
    if "in the style of" in query_lower:
        return True

    # Check for *istic pattern (e.g., "expressionistic", "impressionistic")
    istic_matches = re.findall(r'\b\w+istic\b', query_lower)
    if istic_matches:
        return True

    # Check for *esque pattern, excluding common non-art words
    esque_matches = re.findall(r'\b\w+esque\b', query_lower)
    for match in esque_matches:
        if match not in _NON_ART_ESQUE_WORDS:
            return True

    return False


def resolve_embedding_model(
    model: EmbeddingModelChoice,
    *,
    is_similarity_search: bool = False,
    query: str | None = None
) -> ResolvedEmbeddingModel:
    """
    Resolve 'auto' to the actual model based on context.

    For explicit model choices ("clip" or "jina"), returns as-is.
    For "auto", uses smart selection:
    - Similarity search → Jina
    - Art historical text query → CLIP
    - Other text queries → Jina
    """
    if model == "clip":
        return "clip"
    if model == "jina":
        return "jina"

    # model == "auto": smart selection
    if is_similarity_search:
        return "jina"

    if query and is_art_historical_query(query):
        return "clip"

    return "jina"


MODEL_TO_VECTOR_NAME = {
    "clip": "image_clip",
    "jina": "image_jina",
}
