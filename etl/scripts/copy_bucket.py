"""
Script to copy all objects from one Linode Object Storage bucket to another.

Usage:
    # Preview what would be copied
    python etl/scripts/copy_bucket.py \
        --source-bucket semantic-art-thumbnails-dev-v1 \
        --dest-bucket semantic-art-thumbnails-dev-v2 \
        --dry-run

    # Actually perform the copy
    python etl/scripts/copy_bucket.py \
        --source-bucket semantic-art-thumbnails-dev-v1 \
        --dest-bucket semantic-art-thumbnails-dev-v2

    # Use different region
    python etl/scripts/copy_bucket.py \
        --source-bucket my-source-bucket \
        --dest-bucket my-dest-bucket \
        --region nl-ams-1
"""

import argparse
import time
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from artsearch.src.config import config


def create_s3_client(region: str, aws_access_key_id: str, aws_secret_access_key: str):
    """Create boto3 S3 client configured for Linode Object Storage."""
    boto3_cfg = Config(
        signature_version="s3v4",
        connect_timeout=60,
        read_timeout=60,
        s3={"addressing_style": "virtual"},
    )

    endpoint_url = f"https://{region}.linodeobjects.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        config=boto3_cfg,
    )


def bucket_exists(s3_client, bucket_name: str) -> bool:
    """
    Check if a bucket exists and is accessible.
    Uses list_objects_v2 instead of head_bucket to avoid permission issues.
    """
    try:
        s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket"):
            return False
        # If it's a 403, the bucket might exist but we don't have permission
        # Treat this as "exists" since we'll get a better error message later
        if error_code == "403":
            return True
        raise


def create_bucket(s3_client, bucket_name: str) -> None:
    """Create a new bucket."""
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"✓ Created bucket: {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            print(f"✓ Bucket already exists: {bucket_name}")
        else:
            raise


def list_all_objects(s3_client, bucket_name: str) -> list[dict]:
    """List all objects in a bucket using pagination."""
    objects = []
    continuation_token = None

    while True:
        if continuation_token:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name, ContinuationToken=continuation_token
            )
        else:
            response = s3_client.list_objects_v2(Bucket=bucket_name)

        if "Contents" in response:
            objects.extend(response["Contents"])

        if not response.get("IsTruncated"):
            break

        continuation_token = response.get("NextContinuationToken")

    return objects


def copy_object(
    s3_client, source_bucket: str, dest_bucket: str, key: str, dry_run: bool
) -> bool:
    """
    Copy a single object from source to destination bucket.

    Returns True if successful, False otherwise.
    """
    if dry_run:
        print(f"  [DRY RUN] Would copy: {key}")
        return True

    try:
        # Get source object metadata
        source_metadata = s3_client.head_object(Bucket=source_bucket, Key=key)

        # Copy object with metadata
        s3_client.copy_object(
            Bucket=dest_bucket,
            CopySource={"Bucket": source_bucket, "Key": key},
            Key=key,
            MetadataDirective="COPY",
            ACL=source_metadata.get("ACL", "public-read"),
        )
        return True
    except ClientError as e:
        print(f"  ✗ Failed to copy {key}: {e}")
        return False


def format_size(size_bytes: int | float) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def copy_bucket(
    source_bucket: str,
    dest_bucket: str,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """
    Copy all objects from source bucket to destination bucket.

    Args:
        source_bucket: Name of source bucket
        dest_bucket: Name of destination bucket
        region: Linode region (e.g., 'eu-central-1')
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        dry_run: If True, only preview what would be copied
        batch_size: Number of objects to process per batch

    Returns:
        Dictionary with copy statistics
    """
    start_time = time.time()

    # Create S3 client
    s3_client = create_s3_client(region, aws_access_key_id, aws_secret_access_key)

    # Verify source bucket exists
    print(f"\n📦 Checking source bucket: {source_bucket}")
    if not bucket_exists(s3_client, source_bucket):
        raise ValueError(f"Source bucket does not exist: {source_bucket}")
    print("✓ Source bucket exists")

    # Create destination bucket if needed
    print(f"\n📦 Checking destination bucket: {dest_bucket}")
    if not bucket_exists(s3_client, dest_bucket):
        if dry_run:
            print(f"[DRY RUN] Would create bucket: {dest_bucket}")
        else:
            create_bucket(s3_client, dest_bucket)
    else:
        print("✓ Destination bucket exists")

    # List all objects in source bucket
    print(f"\n📋 Listing objects in {source_bucket}...")
    objects = list_all_objects(s3_client, source_bucket)

    if not objects:
        print("✓ Source bucket is empty, nothing to copy")
        return {"total": 0, "success": 0, "failed": 0}

    total_size = sum(obj["Size"] for obj in objects)
    print(f"✓ Found {len(objects)} objects ({format_size(total_size)})")

    if dry_run:
        print("\n🔍 DRY RUN MODE - No objects will be copied")

    # Copy objects in batches
    print("\n📤 Copying objects...")
    success_count = 0
    failed_count = 0

    for i in range(0, len(objects), batch_size):
        batch = objects[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(objects) + batch_size - 1) // batch_size

        print(f"\n--- Batch {batch_num}/{total_batches} ---")

        for obj in batch:
            key = obj["Key"]
            size = obj["Size"]

            if copy_object(s3_client, source_bucket, dest_bucket, key, dry_run):
                success_count += 1
                if not dry_run:
                    print(f"  ✓ Copied: {key} ({format_size(size)})")
            else:
                failed_count += 1

    # Summary
    duration = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"✓ Copy {'preview' if dry_run else 'operation'} complete!")
    print(f"{'=' * 60}")
    print(f"Total objects: {len(objects)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Total size: {format_size(total_size)}")
    print(f"Duration: {duration:.1f} seconds")

    if dry_run:
        print("\n💡 Run without --dry-run to actually perform the copy")

    return {
        "total": len(objects),
        "success": success_count,
        "failed": failed_count,
        "total_size_bytes": total_size,
        "duration_seconds": duration,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Copy all objects from one Linode bucket to another",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--source-bucket",
        type=str,
        required=True,
        help="Source bucket name (e.g., semantic-art-thumbnails-dev-v1)",
    )

    parser.add_argument(
        "--dest-bucket",
        type=str,
        required=True,
        help="Destination bucket name (will be created if doesn't exist)",
    )

    parser.add_argument(
        "--region",
        type=str,
        default=config.aws_region_etl,
        help=f"Linode region (default: {config.aws_region_etl})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be copied without actually copying",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of objects to process per batch (default: 100)",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt and proceed automatically",
    )

    args = parser.parse_args()

    # Confirm operation unless dry run or --yes flag
    if not args.dry_run and not args.yes:
        print("\n⚠️  WARNING: This will copy all objects from:")
        print(f"   Source: {args.source_bucket}")
        print(f"   Destination: {args.dest_bucket}")
        print(f"   Region: {args.region}")
        confirmation = input("\nDo you want to continue? [y/N]: ")
        if confirmation.lower() != "y":
            print("❌ Operation cancelled")
            return

    # Perform copy
    copy_bucket(
        source_bucket=args.source_bucket,
        dest_bucket=args.dest_bucket,
        region=args.region,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
