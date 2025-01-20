import numpy as np

# Load the embeddings from the .npy file
embeddings = np.load("data/embeddings.npy")

# Print the shape of the embeddings
print(embeddings.shape)

# Print the first embedding
print(embeddings[0])

# get euclidian length of the embedding
print(np.linalg.norm(embeddings[0]))
