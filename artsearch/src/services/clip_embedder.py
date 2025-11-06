import time
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import requests
from typing import Tuple, Any
from functools import lru_cache
import clip
import torch
from artsearch.src.utils.session_config import get_configured_session
from artsearch.src.config import ClipSelection
from artsearch.src.config import config


class ImageDownloadError(Exception):
    """Custom exception for image download failures."""

    pass


class CLIPEmbedder:
    """A class for generating image embeddings using OpenAI's CLIP model."""

    _instantiated = False

    def __new__(cls, *args, **kwargs):
        """Ensure that only one instance of CLIPEmbedder is created."""
        if cls._instantiated:
            raise RuntimeError(
                "Use get_clip_embedder() instead of creating CLIPEmbedder directly."
            )
        cls._instantiated = True
        return super().__new__(cls)

    def __init__(
        self,
        model_name: ClipSelection,
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
            http_session (requests.Session): Shared HTTP session for all requests.
        """
        self.model_name: ClipSelection = model_name
        self.device = device or config.device
        self.model, self.preprocess = self._load_model(model_name, self.device)
        self.embedding_dim = self.model.visual.proj.shape[1]
        self.http_session = http_session or get_configured_session()

    def _load_model(self, model_name: str, device: str) -> Tuple[Any, Any]:
        """Load the CLIP model and preprocessor (caches model by default)."""
        start_time = time.time()
        print(f"Loading CLIP model: {model_name}")
        model, preprocess = clip.load(model_name, device=device)
        print(f"Model loaded on in {time.time() - start_time:.2f}s")
        return model, preprocess

    def _download_image(self, url: str) -> Image.Image:
        """Download an image from a URL.
        Raises an exception if the request fails or the image cannot be processed.
        """
        try:
            response = get_image_response(url)
            response.raise_for_status()

            if not response.content:  # Handle empty responses
                raise ImageDownloadError(f"Empty response from URL: {url}")

            image_bytes = response.content

            return Image.open(BytesIO(image_bytes)).convert("RGB")

        except requests.RequestException as e:
            raise ImageDownloadError(f"Error downloading image from {url}: {e}")

        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageDownloadError(f"Invalid or corrupted image from {url}: {e}")

    def generate_thumbnail_embedding(
        self,
        thumbnail_url: str,
        object_number: str,
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
            img = self._download_image(thumbnail_url)
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
            query (str): The input text to encode.

        Returns:
            list[float]: The text embedding as a list.
        """
        return _generate_text_embedding_cached(self.model, self.device, query)


# Maxsize is set to 50 to cache the most common queries
# Should be at least 1 to cache the item in question on infinite scroll
@lru_cache(maxsize=50)
def _generate_text_embedding_cached(model: Any, device: str, query: str) -> list[float]:
    """
    Pure function for generating text embeddings with LRU caching.

    This function is separated from the class method to enable proper caching
    without relying on the singleton pattern.

    Args:
        model: The CLIP model instance.
        device (str): Device to run the model on ("cuda" or "cpu").
        query (str): The input text to encode.

    Returns:
        list[float]: The text embedding as a list.
    """
    text = clip.tokenize([query]).to(device)
    with torch.no_grad():
        return model.encode_text(text).cpu().numpy().flatten().tolist()


@lru_cache(maxsize=1)
def get_image_response(url: str) -> requests.Response:
    response = requests.get(url, timeout=10)
    return response


@lru_cache(maxsize=1)
def get_clip_embedder(
    model_name: ClipSelection = config.clip_model_name,
) -> CLIPEmbedder:
    """
    Always return the same instance of CLIPEmbedder (one per worker).
    """
    return CLIPEmbedder(model_name=model_name)  # Loads only once
