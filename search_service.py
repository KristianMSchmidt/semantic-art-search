from qdrant_client import QdrantClient
from clip_embedder import CLIPEmbedder


class SearchService:
    def __init__(
        self, qdrant_client: QdrantClient, embedder: CLIPEmbedder, collection_name: str
    ):
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.collection_name = collection_name

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
            }
            for hit in hits.points
        ]

    def search_similar_images(self, object_number: str, limit: int = 5) -> list[dict]:
        """Search for similar items based on an image embedding."""
        query_vector = self.embedder.generate_thumbnail_embedding(
            object_number=object_number
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
            for hit in hits.points
        ]
