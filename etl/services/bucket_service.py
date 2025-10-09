import boto3
from botocore.config import Config
import requests
from botocore.exceptions import ClientError
from io import BytesIO
from PIL import Image
from artsearch.src.config import config
from artsearch.src.services.clip_embedder import get_image_response


def resize_image_with_aspect_ratio(
    image_bytes: bytes, max_dimension: int = 800, jpeg_quality: int = 85
) -> bytes:
    """
    Resize image maintaining aspect ratio with max dimension constraint.

    Args:
        image_bytes: Original image bytes
        max_dimension: Maximum dimension (width or height) in pixels
        jpeg_quality: JPEG compression quality (0-100)

    Returns:
        Resized image as JPEG bytes

    Examples:
        - 3000×1000 → 800×267 (width capped)
        - 1000×3000 → 267×800 (height capped)
        - 2000×2000 → 800×800 (square)
    """
    # Open image from bytes
    img = Image.open(BytesIO(image_bytes))

    # Convert to RGB if needed (handles RGBA, grayscale, etc.)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Calculate new dimensions maintaining aspect ratio
    width, height = img.size
    if max(width, height) <= max_dimension:
        # Image is already small enough, just convert format
        output = BytesIO()
        img.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
        return output.getvalue()

    # Calculate scale factor based on longest dimension
    scale_factor = max_dimension / max(width, height)
    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)

    # Resize using high-quality Lanczos algorithm
    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Save to bytes
    output = BytesIO()
    img_resized.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
    return output.getvalue()


def get_bucket_config(use_etl_bucket: bool) -> tuple[str, str]:
    """
    Get bucket name and region based on context.

    Args:
        use_etl_bucket: If True, return ETL bucket config; if False, return app bucket config

    Returns:
        Tuple of (bucket_name, region)
    """
    if use_etl_bucket:
        return config.bucket_name_etl, config.aws_region_etl
    else:
        return config.bucket_name_app, config.aws_region_app


class BucketService:
    def __init__(
        self,
        use_etl_bucket: bool,
        aws_access_key_id: str = config.aws_access_key_id,
        aws_secret_access_key: str = config.aws_secret_access_key,
    ):
        # Select bucket and region based on context
        self.bucket_name, region = get_bucket_config(use_etl_bucket)

        boto3_cfg = Config(
            signature_version="s3",
            connect_timeout=60,
            read_timeout=60,
            s3={"addressing_style": "path"},
        )

        endpoint_url = f"https://{region}.linodeobjects.com"

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=boto3_cfg,
        )

    def upload_thumbnail(
        self, museum: str, object_number: str, museum_image_url: str
    ) -> None:
        key = get_bucket_image_key(museum, object_number)
        resp = get_image_response(museum_image_url)

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(f"Failed to download {museum_image_url}: {e}") from e

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            raise ValueError(f"Unexpected content type: {content_type}")
        cache_control = "max-age=2592000"  # 30 days

        # Resize image before upload (with graceful fallback)
        try:
            image_bytes = resize_image_with_aspect_ratio(
                resp.content,
                max_dimension=config.image_max_dimension,
                jpeg_quality=config.image_jpeg_quality,
            )
            content_type = "image/jpeg"  # Always JPEG after resize
        except Exception as e:
            print(f"Warning: Failed to resize image for {museum}:{object_number}: {e}")
            print("Uploading original image as fallback")
            image_bytes = resp.content

        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=image_bytes,
            ACL="public-read",
            ContentType=content_type,
            CacheControl=cache_control,
        )
        print(f"Successfully uploaded {key} to bucket {self.bucket_name}")

    def copy_thumbnail(self, old_key: str, new_key: str) -> None:
        self.s3.copy_object(
            Bucket=self.bucket_name,
            CopySource={"Bucket": self.bucket_name, "Key": old_key},
            Key=new_key,
            MetadataDirective="REPLACE",
            ContentType="image/jpeg",
            CacheControl="max-age=2592000",  # 30 days
            ACL="public-read",
        )

    def delete_keys(self, keys: list[str]) -> None:
        if not keys:
            return

        objects = [{"Key": key} for key in keys]

        try:
            response = self.s3.delete_objects(
                Bucket=self.bucket_name, Delete={"Objects": objects}
            )
            errors = response.get("Errors", [])
            if errors:
                print(f"Errors occurred while deleting keys: {errors}")
        except ClientError as e:
            print(f"Failed to delete keys: {e}")

    def object_exists(self, key: str) -> bool:
        """
        Check if an object exists in the S3 bucket.
        Returns True if object exists, False otherwise.
        """
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            # If object doesn't exist, boto3 raises a 404 ClientError
            if e.response["Error"]["Code"] == "404":
                return False
            # For other errors, re-raise
            raise


def get_bucket_image_key(museum: str, object_number: str) -> str:
    return f"{museum}_{object_number}.jpg"


def get_bucket_image_url(
    museum: str, object_number: str, use_etl_bucket: bool
) -> str:
    """
    Get direct S3 URL for image in bucket.

    Args:
        museum: Museum slug
        object_number: Artwork object number
        use_etl_bucket: If True, use ETL bucket; if False, use app bucket

    Returns:
        Full HTTPS URL to image in bucket
    """
    key = get_bucket_image_key(museum, object_number)
    bucket, region = get_bucket_config(use_etl_bucket)
    return f"https://{region}.linodeobjects.com/{bucket}/{key}"
