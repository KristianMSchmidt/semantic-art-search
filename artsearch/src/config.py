import os
from dotenv import load_dotenv
import torch

# Load environment variables
load_dotenv()


class Config:
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")
    DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
