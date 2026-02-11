import json
import struct
import time

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from artsearch.models import ArtMapData
from artsearch.src.config import config
from artsearch.src.constants.museums import (
    MUSEUM_SLUG_TO_INDEX,
    WORK_TYPE_TO_INDEX,
    OTHER_WORK_TYPE_INDEX,
)
from artsearch.src.services.qdrant_service import QdrantService


PAYLOAD_FIELDS = ["museum", "object_number", "title", "artists", "production_date", "searchable_work_types"]


class Command(BaseCommand):
    help = "Generate UMAP 2D coordinates for all artworks (binary geometry + metadata JSON)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--vector-name",
            default="image_jina",
            help="Named vector to use (default: image_jina, 256d)",
        )
        parser.add_argument(
            "--n-neighbors",
            type=int,
            default=15,
            help="UMAP n_neighbors (default: 15)",
        )
        parser.add_argument(
            "--min-dist",
            type=float,
            default=0.03,
            help="UMAP min_dist (default: 0.03)",
        )

    def handle(self, *args, **options):
        vector_name = options["vector_name"]
        n_neighbors = options["n_neighbors"]
        min_dist = options["min_dist"]

        self.stdout.write(f"Fetching points from Qdrant (vector: {vector_name})...")

        qdrant = QdrantService(collection_name=config.qdrant_collection_name_app)

        vectors = []
        museums = []
        object_numbers = []
        titles = []
        artists = []
        production_dates = []
        work_types = []

        next_token = None
        batch_num = 0
        fetch_start = time.time()

        while True:
            points, next_token = qdrant.fetch_points(
                next_page_token=next_token,
                limit=1000,
                with_vectors=[vector_name],
                with_payload=PAYLOAD_FIELDS,
            )

            if not points:
                break

            for point in points:
                vec = point.vector
                if isinstance(vec, dict):
                    vec = vec.get(vector_name)
                if vec is None:
                    continue

                payload = point.payload or {}
                museum_slug = payload.get("museum", "")
                if museum_slug not in MUSEUM_SLUG_TO_INDEX:
                    continue

                vectors.append(vec)
                museums.append(MUSEUM_SLUG_TO_INDEX[museum_slug])
                object_numbers.append(payload.get("object_number", ""))
                titles.append(payload.get("title", ""))

                artist_list = payload.get("artists", [])
                artist_str = artist_list[0] if artist_list else "Unknown"
                artists.append(artist_str)

                production_dates.append(payload.get("production_date", ""))

                swt = payload.get("searchable_work_types", [])
                wt_idx = OTHER_WORK_TYPE_INDEX
                for wt in swt:
                    if wt in WORK_TYPE_TO_INDEX:
                        wt_idx = WORK_TYPE_TO_INDEX[wt]
                        break
                work_types.append(wt_idx)

            batch_num += 1
            if batch_num % 10 == 0:
                self.stdout.write(f"  Fetched {len(vectors):,} points...")

            if next_token is None:
                break

        fetch_time = time.time() - fetch_start
        self.stdout.write(
            self.style.SUCCESS(
                f"Fetched {len(vectors):,} points in {fetch_time:.1f}s"
            )
        )

        if len(vectors) == 0:
            raise CommandError("No vectors found. Check vector name and collection.")

        # Run UMAP
        self.stdout.write(
            f"Running UMAP (n_neighbors={n_neighbors}, min_dist={min_dist})..."
        )
        import umap

        embedding_array = np.array(vectors, dtype=np.float32)
        del vectors  # free memory

        umap_start = time.time()
        reducer = umap.UMAP(
            n_components=2,
            metric="cosine",
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            random_state=42,
        )
        coords = reducer.fit_transform(embedding_array)
        umap_time = time.time() - umap_start
        self.stdout.write(
            self.style.SUCCESS(f"UMAP complete in {umap_time:.1f}s")
        )

        del embedding_array  # free memory

        # Normalize to 0-1
        x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
        y_min, y_max = coords[:, 1].min(), coords[:, 1].max()
        coords[:, 0] = (coords[:, 0] - x_min) / (x_max - x_min)
        coords[:, 1] = (coords[:, 1] - y_min) / (y_max - y_min)

        # Build binary geometry payload
        count = len(museums)
        x_scaled = (coords[:, 0] * 1000).astype(np.float32)
        y_scaled = (coords[:, 1] * 1000).astype(np.float32)
        museum_arr = np.array(museums, dtype=np.uint8)
        work_type_arr = np.array(work_types, dtype=np.uint8)

        geometry_blob = (
            struct.pack("<I", count)
            + x_scaled.tobytes()
            + y_scaled.tobytes()
            + museum_arr.tobytes()
            + work_type_arr.tobytes()
        )

        # Build metadata-only JSON
        metadata = {
            "count": count,
            "object_number": object_numbers,
            "title": titles,
            "artist": artists,
            "production_date": production_dates,
        }
        metadata_json = json.dumps(metadata, separators=(",", ":"))

        self.stdout.write("Saving to database...")
        ArtMapData.objects.create(geometry=geometry_blob, metadata=metadata_json)

        geo_mb = len(geometry_blob) / (1024 * 1024)
        meta_mb = len(metadata_json) / (1024 * 1024)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Saved {count:,} artworks to database "
                f"(geometry: {geo_mb:.1f} MB, metadata: {meta_mb:.1f} MB)"
            )
        )
