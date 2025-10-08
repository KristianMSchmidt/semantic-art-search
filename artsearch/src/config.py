import os
from pathlib import Path
import torch
import dotenv
from pydantic import BaseModel
from typing import Literal


ClipSelection = Literal["ViT-L/14"]


class Config(BaseModel):
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str
    django_secret_key: str
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    allowed_hosts: list[str] = []
    debug: bool = False
    clip_model_name: ClipSelection
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    bucket_name: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: str
    # Image processing settings
    image_max_dimension: int = 800
    image_jpeg_quality: int = 85


def create_config():
    env_files = [".env.dev", ".env.prod"]
    for env_file in env_files:
        if Path(env_file).exists():
            dotenv.load_dotenv(env_file)
            break
    else:
        raise FileNotFoundError("No .env file found")

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_collection_name = "artworks_ViTL14_v3"
    django_secret_key = os.getenv("DJANGO_SECRET_KEY")
    device = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    debug = os.getenv("DEBUG", "False").lower() == "true"
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")
    bucket_name = os.getenv("BUCKET_NAME")
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_db = os.getenv("POSTGRES_DB")
    postgres_host = os.getenv("POSTGRES_HOST")
    postgres_port = os.getenv("POSTGRES_PORT")
    # Image processing settings (optional, with defaults)
    image_max_dimension = int(os.getenv("IMAGE_MAX_DIMENSION", "800"))
    image_jpeg_quality = int(os.getenv("IMAGE_JPEG_QUALITY", "85"))

    if not qdrant_url:
        raise ValueError("QDRANT_URL is not set")
    if not qdrant_api_key:
        raise ValueError("QDRANT_API_KEY is not set")
    if not qdrant_collection_name:
        raise ValueError("QDRANT_COLLECTION_NAME is not set")
    if not django_secret_key:
        raise ValueError("DJANGO_SECRET_KEY is not set")
    if not allowed_hosts:
        raise ValueError("ALLOWED_HOSTS is not set")
    if not aws_access_key_id:
        raise ValueError("AWS_ACCESS_KEY_ID is not set")
    if not aws_secret_access_key:
        raise ValueError("AWS_SECRET_ACCESS_KEY is not set")
    if not aws_region:
        raise ValueError("AWS_REGION is not set")
    if not bucket_name:
        raise ValueError("BUCKET_NAME is not set")
    if not postgres_user:
        raise ValueError("POSTGRES_USER is not set")
    if not postgres_password:
        raise ValueError("POSTGRES_PASSWORD is not set")
    if not postgres_db:
        raise ValueError("POSTGRES_DB is not set")
    if not postgres_host:
        raise ValueError("POSTGRES_HOST is not set")
    if not postgres_port:
        raise ValueError("POSTGRES_PORT is not set")

    return Config(
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        qdrant_collection_name=qdrant_collection_name,
        django_secret_key=django_secret_key,
        device=device,
        allowed_hosts=allowed_hosts,
        debug=debug,
        clip_model_name="ViT-L/14",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region=aws_region,
        bucket_name=bucket_name,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        postgres_db=postgres_db,
        postgres_port=postgres_port,
        postgres_host=postgres_host,
        image_max_dimension=image_max_dimension,
        image_jpeg_quality=image_jpeg_quality,
    )


config = create_config()

if __name__ == "__main__":
    config = create_config()
    print(config)
