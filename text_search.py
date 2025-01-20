import clip
import torch
import numpy as np
import pandas as pd
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
    return model


def get_query_embedding(query, model, device):
    """Generate an embedding for the user query using the CLIP model."""
    text = clip.tokenize([query]).to(device)
    with torch.no_grad():
        return model.encode_text(text).cpu().numpy().flatten()


def get_top_matches(query_embedding, embeddings, metadata, top_n=10):
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
    print("Loading model...")
    model = load_model(device)
    print("Model loaded successfully.")

    # Interactive query loop
    while True:
        query = input("Enter your query (or type 'exit' to quit): ")
        if query.lower() == 'exit':
            print("Exiting the program. Goodbye!")
            break

        # Get query embedding
        query_embedding = get_query_embedding(query, model, device)

        # Retrieve and display top results
        top_results = get_top_matches(query_embedding, embeddings, metadata)
        print(top_results[['title', 'artist', 'object_name', 'image_path']])
        print()


if __name__ == "__main__":
    main()
