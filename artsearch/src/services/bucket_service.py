import boto3
from botocore.config import Config
import requests
from urllib.parse import urlparse
from artsearch.src.config import config

session = requests.Session()

boto3_cfg = Config(
    signature_version="s3",
    connect_timeout=60,
    read_timeout=60,
    s3={"addressing_style": "path"},
)


s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{config.aws_region}.linodeobjects.com",
    region_name=config.aws_region,
    aws_access_key_id=config.aws_access_key_id,
    aws_secret_access_key=config.aws_secret_access_key,
    config=boto3_cfg,
)


def get_bucket_thumbnail_url(
    museum_image_url: str,
    bucket_name: str = config.bucket_name,
    aws_region: str = config.aws_region,
) -> str:
    """
    Get the bucket URL for a thumbnail url
    """
    filename = urlparse(museum_image_url).path.lstrip("/").replace("/", "_")
    return f"https://{bucket_name}.{aws_region}.linodeobjects.com/{filename}"


def upload_thumbnail(
    museum_image_url: str,
    bucket_name: str = config.bucket_name,
    aws_region: str = config.aws_region,
) -> str:
    """
    Upload a thumbnail to the bucket (streaming), set content-type & cache headers,
    and return the public URL. Overwrites any existing object with the same key.
    """
    key = urlparse(museum_image_url).path.lstrip("/").replace("/", "_")
    bucket_url = f"https://{bucket_name}.{aws_region}.linodeobjects.com/{key}"

    # Stream the download to avoid big memory spikes
    resp = session.get(museum_image_url, stream=True, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Failed to download {museum_image_url}: {e}") from e

    content_type = resp.headers.get("Content-Type", "application/octet-stream")
    cache_control = "max-age=31536000"  # 1 year

    # Upload via upload_fileobj to leverage streaming
    s3.upload_fileobj(
        Fileobj=resp.raw,
        Bucket=bucket_name,
        Key=key,
        ExtraArgs={
            "ACL": "public-read",
            "ContentType": content_type,
            "CacheControl": cache_control,
        },
    )

    return bucket_url
