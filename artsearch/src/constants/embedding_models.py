from typing import Literal

EmbeddingModelChoice = Literal["auto", "clip", "jina"]

EMBEDDING_MODELS = [
    {"value": "auto", "label": "Auto", "description": "Automatic (currently CLIP)"},
    {"value": "clip", "label": "CLIP", "description": "OpenAI CLIP"},
    {"value": "jina", "label": "Jina", "description": "Jina CLIP v2"},
]

DEFAULT_EMBEDDING_MODEL: EmbeddingModelChoice = "auto"


def resolve_embedding_model(model: EmbeddingModelChoice) -> Literal["clip", "jina"]:
    """Resolve 'auto' to the actual model."""
    if model == "auto":
        return "clip"
    return model


MODEL_TO_VECTOR_NAME = {
    "clip": "image_clip",
    "jina": "image_jina",
}
