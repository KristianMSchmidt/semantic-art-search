import clip
import torch

import numpy as np
import pandas as pd

# Load the metadata
csv_path = "data/meta_data.csv"
data = pd.read_csv(csv_path)

# Load embeddings
embeddings = np.load("embeddings.npy")

# Check the shape of the embeddings
print(f"Loaded embeddings shape: {embeddings.shape}")
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
print("Model loaded")
# Get the query embedding from user command line input
query = input("Enter your query: ")


text = clip.tokenize([query]).to(device)

with torch.no_grad():
    query_embedding = model.encode_text(text).cpu().numpy().flatten()

from sklearn.metrics.pairwise import cosine_similarity

# Calculate cosine similarity
similarities = cosine_similarity(query_embedding.reshape(1, -1), embeddings)

# Sort results by similarity
top_indices = similarities.argsort()[0][::-1]  # Highest similarity first
top_results = data.iloc[top_indices[:5]]  # Retrieve top 5 results

print(top_results[['title', 'artist', 'image_path', 'thumbnail_path']])
