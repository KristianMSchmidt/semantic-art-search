import clip
import torch
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity


def load_data(csv_path, embeddings_path):
    """Load metadata and embeddings from specified paths."""
    metadata = pd.read_csv(csv_path)
    embeddings = np.load(embeddings_path)
    print(f"Loaded embeddings shape: {embeddings.shape}")
    return metadata, embeddings


def load_model(device):
    """Load the CLIP model and preprocessing pipeline."""
    model, preprocess = clip.load("ViT-B/32", device=device)
    print("Model loaded")
    return model, preprocess


def get_image_embedding(image_path, model, preprocess, device):
    """Generate an embedding for an image using the CLIP model."""
    try:
        image = Image.open(image_path)
        image_tensor = preprocess(image).unsqueeze(0).to(device)
        with torch.no_grad():
            embedding = model.encode_image(image_tensor).cpu().numpy().flatten()
        return embedding
    except Exception as e:
        raise FileNotFoundError(f"Could not process image {image_path}: {e}")


def get_top_matches(query_embedding, embeddings, metadata, top_n=5):
    """Calculate cosine similarities and return the top matches."""
    similarities = cosine_similarity(query_embedding.reshape(1, -1), embeddings)
    top_indices = similarities.argsort()[0][::-1]  # Sort in descending order
    # Print similarity scores
    for i in range(top_n):
        print(f"Top-{i+1} Similarity: {similarities[0][top_indices[i]]:.3f}")
    return metadata.iloc[top_indices[:top_n]]


def main():
    # File paths
    csv_path = "data/metadata.csv"
    embeddings_path = "data/embeddings.npy"

    # Load data
    metadata, embeddings = load_data(csv_path, embeddings_path)

    # Initialize model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = load_model(device)

    # Get object_number from user
    # object_number = input("Enter object_number: ")
    object_number = "KMS1356"
    image_path = f"data/images/{object_number}.jpg"

    # Get image embedding
    try:
        query_embedding = get_image_embedding(image_path, model, preprocess, device)
    except FileNotFoundError as e:
        print(e)
        return

    # Retrieve and display top results
    top_results = get_top_matches(query_embedding, embeddings, metadata)
    print("\nTop 5 similar images:")
    print(top_results[['title', 'artist', 'object_name', 'image_path']])


if __name__ == "__main__":
    main()
