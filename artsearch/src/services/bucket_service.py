import boto3
from botocore.config import Config
import requests
from botocore.exceptions import ClientError
from artsearch.src.config import config
from artsearch.src.services.clip_embedder import get_image_response


class BucketService:
    def __init__(
        self,
        bucket_name: str = config.bucket_name,
        region: str = config.aws_region,
        aws_access_key_id: str = config.aws_access_key_id,
        aws_secret_access_key: str = config.aws_secret_access_key,
    ):
        self.bucket_name = bucket_name

        boto3_cfg = Config(
            signature_version="s3",
            connect_timeout=60,
            read_timeout=60,
            s3={"addressing_style": "path"},
        )

        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{region}.linodeobjects.com",
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
        cache_control = "max-age=31536000"  # 1 year

        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=resp.content,
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
            CacheControl="max-age=31536000",  # 1 year
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


def get_bucket_image_key(museum: str, object_number: str) -> str:
    return f"{museum}_{object_number}.jpg"


def get_cdn_thumbnail_url(museum: str, object_number: str) -> str:
    key = get_bucket_image_key(museum=museum, object_number=object_number)
    return f"https://cdn.kristianms.com/{key}"
