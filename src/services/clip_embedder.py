from PIL import Image
from io import BytesIO
import requests
import clip
import torch
import os


class CLIPEmbedder:
    """A class for generating image embeddings using OpenAI's CLIP model."""

    def __init__(
        self,
        model_name: str = "ViT-B/32",
        device: str = None,
        cache_dir: str = "data/images",
    ):
        """
        Initialize the CLIPEmbedder with the specified model, device, and cache
        directory.

        Args:
            model_name (str): The name of the CLIP model to load (default: "ViT-B/32").
            device (str): Device to run the model on ("cuda" or "cpu"). If None, it is
            auto-detected.
            cache_dir (str): Directory to store cached images.
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.cache_dir = cache_dir

    def _get_local_image_path(self, object_number: str) -> str:
        """Return the local file path for a cached image."""
        return os.path.join(self.cache_dir, f"{object_number}.jpg")

    def _download_image(self, url: str, save_path: str) -> Image.Image:
        """Download an image from a URL and save it locally."""
        response = requests.get(url)
        response.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(response.content)
        return Image.open(BytesIO(response.content)).convert("RGB")

    def _load_image(self, thumbnail_url: str, object_number: str) -> Image.Image:
        """Load an image from the cache or download it."""
        local_path = self._get_local_image_path(object_number)

        if os.path.exists(local_path):
            print(f"Using cached image: {local_path}")
            return Image.open(local_path).convert("RGB")
        else:
            print(f"Downloading image from URL: {thumbnail_url}")
            return self._download_image(thumbnail_url, local_path)

    def generate_thumbnail_embedding(
        self, thumbnail_url: str, object_number: str
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
            img = self._load_image(thumbnail_url, object_number)
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
