import numpy as np
from qdrant_client import QdrantClient
from artsearch.src.services.clip_embedder import CLIPEmbedder
from artsearch.src.services.smk_api_client import SMKAPIClient


class QdrantSearchService:

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedder: CLIPEmbedder,
        smk_api_client: SMKAPIClient,
        collection_name: str,
    ):
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.collection_name = collection_name
        self.smk_api_client = smk_api_client


    def _format_hits(self, hits) -> list[dict]:
        """Format the search hits into a consistent dictionary structure."""
        return [
            {
                "score": round(hit.score, 3),
                "title": hit.payload['titles'][0]['title'],
                "artist": hit.payload['artist'],
                "thumbnail_url": hit.payload['thumbnail_url'],
                "production_date_start": hit.payload['production_date_start'],
                "production_date_end": hit.payload['production_date_end'],
                "object_number": hit.payload['object_number'],
            }
            for hit in hits.points
        ]

    def search_text(self, query: str, limit: int = 5) -> list[dict]:
        """Search for similar items based on a text query."""
        query_vector = self.embedder.generate_text_embedding(query)
        hits = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
        )
        return self._format_hits(hits)

    def search_similar_images(self, object_number: str, limit: int = 6) -> list[dict]:
        """Search for similar items based on an image embedding."""
        thumbnail_url = self.smk_api_client.get_thumbnail_url(object_number)
        query_vector = self.embedder.generate_thumbnail_embedding(
            thumbnail_url, object_number
        )
        hits = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
        )
        return self._format_hits(hits)

    def get_random_point(self) -> dict:
        """Get a random point from the collection."""

        embedding_dim = 512

        # Generate a random query vector
        random_query_vector = np.random.rand(embedding_dim).tolist()

        # Search for the nearest point to the random query vector
        result = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=random_query_vector,
            limit=1
        )

        return self._format_hits(result)[0]
