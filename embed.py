import pandas as pd
from PIL import Image
import clip
import torch
import numpy as np


def load_metadata(csv_path: str) -> pd.DataFrame:
    """Load metadata from a CSV file."""
    try:
        return pd.read_csv(csv_path)
    except Exception as e:
        raise FileNotFoundError(f"Failed to load metadata from {csv_path}: {e}")


def load_clip_model(device: str):
    """Load the CLIP model and preprocessing."""
    model, preprocess = clip.load("ViT-B/32", device=device)
    return model, preprocess


def generate_embeddings(
    data: pd.DataFrame, model, preprocess, device: str
) -> np.ndarray:
    """Generate embeddings for images specified in the metadata."""
    embeddings = []

    for _, row in data.iterrows():
        image_path = row.get('image_path')
        if not image_path:
            print(f"No image path specified for row: {row}")
            embeddings.append(None)
            continue

        try:
            # Load and preprocess the image
            image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)

            # Generate embedding
            with torch.no_grad():
                embedding = model.encode_image(image).cpu().numpy().flatten()
            embeddings.append(embedding)
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            embeddings.append(None)  # Add None for failed images

    # Filter out None values and convert to NumPy array
    return np.array([emb for emb in embeddings if emb is not None])


def save_embeddings(embeddings: np.ndarray, output_path: str):
    """Save embeddings to a file."""
    try:
        np.save(output_path, embeddings)
        print(f"Embeddings saved to {output_path}")
    except Exception as e:
        raise IOError(f"Failed to save embeddings to {output_path}: {e}")


def main():
    # Configuration
    csv_path = "data/meta_data.csv"
    output_path = "data/embeddings2.npy"

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Load metadata
    print("Loading metadata...")
    data = load_metadata(csv_path)

    # Load model and preprocessing
    print("Loading CLIP model...")
    model, preprocess = load_clip_model(device)

    # Generate embeddings
    print("Generating embeddings...")
    embeddings = generate_embeddings(data, model, preprocess, device)

    # Save embeddings
    print("Saving embeddings...")
    save_embeddings(embeddings, output_path)

    print("Done!")


if __name__ == "__main__":
    main()
