import os
from pathlib import Path
import torch
import dotenv

# Load environment variables
if Path(".env.dev").exists():
    dotenv.load_dotenv(".env.dev")
elif Path(".env.prod").exists():
    dotenv.load_dotenv(".env.prod")
else:
    raise Exception("No .env file found")


class Config:
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")
    DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    SECRET_KEY = os.getenv('SECRET_KEY')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
