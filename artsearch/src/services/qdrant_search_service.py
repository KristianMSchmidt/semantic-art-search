from qdrant_client import QdrantClient, models
from qdrant_client.http.models.models import ScoredPoint, Payload
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

    def _format_payload(self, payload: Payload | None) -> dict:
        assert payload
        if payload['production_date_start'] == payload['production_date_end']:
            period = payload['production_date_start']
        else:
            period = (
                f"{payload['production_date_start']} - {payload['production_date_end']}"
            )

        return {
            "title": payload['titles'][0]['title'],
            "artist": payload['artist'][0],
            "thumbnail_url": payload['thumbnail_url'],
            "period": period,
            "object_number": payload['object_number'],
        }

    def _format_payloads(self, payloads: list[Payload | None]) -> list[dict]:
        return [self._format_payload(payload) for payload in payloads]

    def _format_hit(self, hit: ScoredPoint) -> dict:
        formatted_hit = self._format_payload(hit.payload)
        formatted_hit.update({"score": round(hit.score, 3)})
        return formatted_hit

    def _format_hits(self, hits: list[ScoredPoint]) -> list[dict]:
        return [self._format_hit(hit) for hit in hits]

    def _get_vector_by_object_number(self, object_number: str) -> list[float] | None:
        """Get the vector for an object number if it exists in the collection."""
        result = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=None,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="object_number",
                        match=models.MatchValue(value=object_number),
                    ),
                ]
            ),
            limit=1,
            with_payload=False,
            with_vectors=True,
        )
        if result.points == []:
            return None
        else:
            return result.points[0].vector  # type: ignore

    def search_text(self, query: str, limit: int = 5) -> list[dict]:
        """Search for similar items based on a text query."""
        query_vector = self.embedder.generate_text_embedding(query)
        hits = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
        )
        return self._format_hits(hits.points)

    def search_similar_images(self, object_number: str, limit: int = 6) -> list[dict]:
        """Search for similar items based on an image embedding."""
        query_vector = self._get_vector_by_object_number(object_number)

        if query_vector is None:
            thumbnail_url = self.smk_api_client.get_thumbnail_url(object_number)
            query_vector = self.embedder.generate_thumbnail_embedding(
                thumbnail_url, object_number, cache=False
            )

        hits = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
        )
        return self._format_hits(hits.points)

    def get_random_sample(self, limit=10) -> list[dict]:
        """Get a random sample of items from the collection."""
        sampled = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=models.SampleQuery(sample=models.Sample.RANDOM),
            with_vectors=False,
            with_payload=True,
            limit=limit,
        )
        payloads = [point.payload for point in sampled.points]
        return self._format_payloads(payloads)
