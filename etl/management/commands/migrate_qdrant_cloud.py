"""
Management command to migrate Qdrant data from Cloud to local instance.

This script:
1. Connects to Qdrant Cloud and local Qdrant instance
2. Creates the collection locally with the same structure
3. Scrolls through all points in the cloud collection
4. Uploads them to the local instance in batches
"""

from django.core.management.base import BaseCommand
from qdrant_client import QdrantClient, models
from artsearch.src.config import config
import time


class Command(BaseCommand):
    help = "Migrate Qdrant collection from Cloud to local instance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cloud-url",
            type=str,
            default=config.qdrant_url,
            help="Qdrant Cloud URL (default: from QDRANT_URL env var)",
        )
        parser.add_argument(
            "--cloud-api-key",
            type=str,
            default=config.qdrant_api_key,
            help="Qdrant Cloud API key (default: from QDRANT_API_KEY env var)",
        )
        parser.add_argument(
            "--local-url",
            type=str,
            default="http://localhost:6333",
            help="Local Qdrant URL (default: http://localhost:6333)",
        )
        parser.add_argument(
            "--collection-name",
            type=str,
            default="artworks_prod_v1",
            help="Collection name to migrate (default: artworks_prod_v1)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of points to process in each batch (default: 100)",
        )
        parser.add_argument(
            "--skip-collection-creation",
            action="store_true",
            help="Skip collection creation (useful if collection already exists locally)",
        )

    def handle(self, *args, **options):
        cloud_url = options["cloud_url"]
        cloud_api_key = options["cloud_api_key"]
        local_url = options["local_url"]
        collection_name = options["collection_name"]
        batch_size = options["batch_size"]
        skip_collection_creation = options["skip_collection_creation"]

        self.stdout.write(f"Migrating Qdrant collection: {collection_name}")
        self.stdout.write(f"Cloud URL: {cloud_url}")
        self.stdout.write(f"Local URL: {local_url}")
        self.stdout.write(f"Batch size: {batch_size}")
        self.stdout.write("")

        # Connect to cloud and local instances
        self.stdout.write("Connecting to Qdrant Cloud...")
        cloud_client = QdrantClient(url=cloud_url, api_key=cloud_api_key)

        self.stdout.write("Connecting to local Qdrant...")
        local_client = QdrantClient(url=local_url)

        # Get collection info from cloud
        self.stdout.write(f"Getting collection info from cloud...")
        try:
            cloud_collection = cloud_client.get_collection(collection_name)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to get collection from cloud: {e}"))
            return

        self.stdout.write(f"Cloud collection info:")
        self.stdout.write(f"  Points count: {cloud_collection.points_count}")
        self.stdout.write(f"  Vectors config: {cloud_collection.config.params.vectors}")
        self.stdout.write("")

        # Create collection locally (if not skipped)
        if not skip_collection_creation:
            self.stdout.write(f"Creating collection '{collection_name}' on local instance...")
            try:
                local_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=cloud_collection.config.params.vectors,
                )
                self.stdout.write(self.style.SUCCESS("Collection created successfully"))

                # Create payload indices for filtering performance
                self.stdout.write("Creating payload indices...")
                try:
                    local_client.create_payload_index(
                        collection_name=collection_name,
                        field_name="museum",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    local_client.create_payload_index(
                        collection_name=collection_name,
                        field_name="searchable_work_types",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    local_client.create_payload_index(
                        collection_name=collection_name,
                        field_name="object_number",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    self.stdout.write(self.style.SUCCESS("Payload indices created successfully"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed to create indices: {e}"))

            except Exception as e:
                if "already exists" in str(e).lower():
                    self.stdout.write(self.style.WARNING(f"Collection already exists locally, continuing..."))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to create collection: {e}"))
                    return
        else:
            self.stdout.write("Skipping collection creation (--skip-collection-creation)")

        # Scroll through all points and upload to local
        self.stdout.write(f"\nStarting migration...")
        next_page_offset = None
        total_points = 0
        batch_count = 0
        start_time = time.time()

        while True:
            # Fetch batch from cloud
            try:
                points, next_page_offset = cloud_client.scroll(
                    collection_name=collection_name,
                    scroll_filter=None,
                    with_payload=True,
                    with_vectors=True,
                    limit=batch_size,
                    offset=next_page_offset,
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to scroll cloud collection: {e}"))
                break

            if not points:
                break

            batch_count += 1
            total_points += len(points)

            # Convert Records to PointStructs for upload
            point_structs = [
                models.PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=point.payload,
                )
                for point in points
            ]

            # Upload to local instance
            try:
                local_client.upsert(
                    collection_name=collection_name,
                    points=point_structs,
                )
                elapsed = time.time() - start_time
                rate = total_points / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"Batch {batch_count}: Uploaded {len(points)} points "
                    f"(total: {total_points}, rate: {rate:.1f} pts/sec)"
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to upload batch: {e}"))
                break

            # Check if there are more pages
            if next_page_offset is None:
                break

        # Final summary
        elapsed = time.time() - start_time
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Migration completed!"))
        self.stdout.write(f"Total points migrated: {total_points}")
        self.stdout.write(f"Total batches: {batch_count}")
        self.stdout.write(f"Time elapsed: {elapsed:.1f}s")
        self.stdout.write(f"Average rate: {total_points/elapsed:.1f} points/sec")

        # Verify local collection
        self.stdout.write("\nVerifying local collection...")
        try:
            local_collection = local_client.get_collection(collection_name)
            self.stdout.write(f"Local collection points count: {local_collection.points_count}")

            if local_collection.points_count == cloud_collection.points_count:
                self.stdout.write(self.style.SUCCESS("✓ Point counts match!"))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ Point count mismatch: cloud={cloud_collection.points_count}, "
                        f"local={local_collection.points_count}"
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to verify local collection: {e}"))
