import boto3
from botocore.config import Config
import requests
from artsearch.src.config import config
from botocore.exceptions import ClientError

session = requests.Session()

boto3_cfg = Config(
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


def get_cdn_thumbnail_url(
    museum: str,
    object_number: str,
) -> str:
    """
    Get the bucket URL for a thumbnail url
    """
    filename = get_bucket_image_key(museum=museum, object_number=object_number)
    return f"https://cdn.kristianms.com/{filename}"


def upload_thumbnail(
    museum: str,
    object_number: str,
    museum_image_url: str,
    bucket_name: str = config.bucket_name,
) -> None:
    """
    Upload a thumbnail to the bucket (streaming), set content-type & cache headers,
    and return the public URL. Overwrites any existing object with the same key.

    TODO: Make a bulk version of this function to upload multiple images at once.
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
    old_key: str,
    new_key: str,
    bucket_name: str = config.bucket_name,
) -> None:
    """
    Copy an image from the old key format to the new key format in the same bucket.
    Keeps the original file and creates a duplicate with the new name.
    """
    s3.copy_object(
        Bucket=bucket_name,
        CopySource={"Bucket": bucket_name, "Key": old_key},
        Key=new_key,
        MetadataDirective="REPLACE",
        ContentType="image/jpeg",
        CacheControl="max-age=31536000",
        ACL="public-read",
    )


def delete_keys(
    keys: list[str],
    bucket_name: str = config.bucket_name,
) -> None:
    """
    Batch delete multiple keys from the bucket.
    """
    if not keys:
        return

    objects = [{"Key": key} for key in keys]
    try:
        response = s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
        deleted = response.get("Deleted", [])
        errors = response.get("Errors", [])
        if errors:
            print(f"Errors occurred while deleting keys: {errors}")

    except ClientError as e:
        print(f"Failed to delete keys: {e}")
