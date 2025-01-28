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

    def search_text(self, query: str, limit: int = 5) -> list[dict]:
        """Search for similar items based on a text query."""
        query_vector = self.embedder.generate_text_embedding(query)
        hits = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
        )
        return [
            {
                "score": hit.score,
                "title": hit.payload['titles'][0]['title'],
                "artist": hit.payload['artist'],
                "thumbnail_url": hit.payload['thumbnail_url'],
                "production_date_start": hit.payload['production_date_start'],
                "production_date_end": hit.payload['production_date_end'],
                "object_number": hit.payload['object_number'],
            }
            for hit in hits.points
        ]

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
        return [
            {
                "score": hit.score,
                "title": hit.payload['titles'][0]['title'],
                "artist": hit.payload['artist'],
                "thumbnail_url": hit.payload['thumbnail_url'],
            }
            for hit in hits.points[1:]
        ]
