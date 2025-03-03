import time
from PIL import Image
from io import BytesIO
import requests
import os
from typing import Tuple, Any
from functools import lru_cache
import clip
import torch
from artsearch.src.utils.session_config import get_configured_session
from artsearch.src.config import clip_selection
from artsearch.src.config import config


class _CLIPEmbedder:
    """A class for generating image embeddings using OpenAI's CLIP model."""

    _instance = None  # Store singleton instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None:
            raise RuntimeError(
                "Use get_clip_embedder() instead of creating CLIPEmbedder directly."
            )
        cls._instance = super(_CLIPEmbedder, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_name: clip_selection,
        cache_dir: str = "data/images",
        http_session: requests.Session | None = None,
        device: str | None = None,
    ):
        """
        Initialize the CLIPEmbedder with the specified model, device, cache
        directory, and HTTP session.

        Args:
            model_name (str): The name of the CLIP model to load.
            device (str): Device to run the model on ("cuda" or "cpu"). If None, it is
            auto-detected.
            cache_dir (str): Directory to store cached images.
            http_session (requests.Session): Shared HTTP session for all requests.
        """
        self.model_name: clip_selection = model_name
        self.device = device or config.device
        self.model, self.preprocess = self._load_model(model_name, self.device)
        self.embedding_dim = self.model.visual.proj.shape[1]
        self.cache_dir = cache_dir
        self.http_session = http_session or get_configured_session()

    def _load_model(self, model_name: str, device: str) -> Tuple[Any, Any]:
        """Load the CLIP model and preprocessor (caches model by default)."""
        start_time = time.time()
        print(f"Loading CLIP model: {model_name}")
        model, preprocess = clip.load(model_name, device=device)
        print(f"Model loaded on in {time.time() - start_time:.2f}s")
        return model, preprocess

    def _get_local_image_path(self, object_number: str) -> str:
        """Return the local file path for a cached image."""
        return os.path.join(self.cache_dir, f"{object_number}.jpg")

    def _download_image(self, url: str, save_path: str, cache: bool) -> Image.Image:
        """Download an image from a URL and optionally save it locally."""
        response = self.http_session.get(url)
        response.raise_for_status()

        image_bytes = response.content

        if cache:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(image_bytes)
            return Image.open(save_path).convert("RGB")

        return Image.open(BytesIO(image_bytes)).convert("RGB")

    def _load_image(
        self, thumbnail_url: str, object_number: str, cache: bool
    ) -> Image.Image:
        """Load an image from the cache or download it."""
        local_path = self._get_local_image_path(object_number)

        if cache and os.path.exists(local_path):
            print(f"Using cached image: {local_path}")
            return Image.open(local_path).convert("RGB")
        else:
            print(f"Downloading image from URL: {thumbnail_url}")
            return self._download_image(thumbnail_url, local_path, cache)

    def generate_thumbnail_embedding(
        self, thumbnail_url: str, object_number: str, cache: bool
    ) -> list[float] | None:
        """
        Generate an image embedding from a URL or cached image.

        Args:
            thumbnail_url (str): URL of the thumbnail image.
            object_number (str): Object number associated with the image.

        Returns:
            list[float]: The embedding vector as a list, or None if an error occurs.
        """
        try:
            img = self._load_image(thumbnail_url, object_number, cache)
            image_tensor = self.preprocess(img).unsqueeze(0).to(self.device)
            with torch.no_grad():
                embedding = (
                    self.model.encode_image(image_tensor).cpu().numpy().flatten()
                )
            return embedding.tolist()
        except Exception as e:
            print(f"Error generating embedding for object {object_number}: {e}")
            return None

    def generate_text_embedding(self, query: str) -> list[float]:
        """
        Generate a text embedding from a given query string.

        Args:
            text (str): The input text to encode.

        Returns:
            list[float]: The text embedding as a list.
        """
        text = clip.tokenize([query]).to(self.device)
        with torch.no_grad():
            return self.model.encode_text(text).cpu().numpy().flatten().tolist()


@lru_cache(maxsize=1)
def get_clip_embedder(
    model_name: clip_selection = config.clip_model_name,
) -> _CLIPEmbedder:
    """
    Always return the same instance of CLIPEmbedder (one per worker).
    """
    return _CLIPEmbedder(model_name=model_name)  # Loads only once
