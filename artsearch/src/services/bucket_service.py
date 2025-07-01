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


def get_bucket_image_key(
    museum: str,
    object_number: str,
) -> str:
    """
    Get the key for an image in the bucket
    """
    filename = f"{museum}_{object_number}.jpg"
    return filename


def get_bucket_thumbnail_url(
    museum: str,
    object_number: str,
    bucket_name: str = config.bucket_name,
    aws_region: str = config.aws_region,
) -> str:
    """
    Get the bucket URL for a thumbnail url
    """
    filename = get_bucket_image_key(museum=museum, object_number=object_number)
    return f"https://{bucket_name}.{aws_region}.linodeobjects.com/{filename}"


def upload_thumbnail(
    museum: str,
    object_number: str,
    museum_image_url: str,
    bucket_name: str = config.bucket_name,
) -> None:
    """
    Upload a thumbnail to the bucket (streaming), set content-type & cache headers,
    and return the public URL. Overwrites any existing object with the same key.
    """
    key = get_bucket_image_key(
        museum=museum,
        object_number=object_number,
    )
    # Stream the download to avoid big memory spikes
    resp = session.get(museum_image_url, stream=True, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Failed to download {museum_image_url}: {e}") from e

    content_type = resp.headers.get("Content-Type", "image/jpeg")

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


def copy_thumbnail(
    museum: str,
    object_number: str,
    museum_image_url: str,
    bucket_name: str = config.bucket_name,
) -> None:
    """
    Copy an image from the old key format to the new key format in the same bucket.
    Keeps the original file and creates a duplicate with the new name.
    """
    old_key = urlparse(museum_image_url).path.lstrip("/").replace("/", "_")

    new_key = get_bucket_image_key(
        museum=museum,
        object_number=object_number,
    )
    s3.copy_object(
        Bucket=bucket_name,
        CopySource={"Bucket": bucket_name, "Key": old_key},
        Key=new_key,
        MetadataDirective="REPLACE",
        ContentType="image/jpeg",
        CacheControl="max-age=31536000",
        ACL="public-read",
    )
