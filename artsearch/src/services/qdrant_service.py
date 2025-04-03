from typing import cast
from qdrant_client import QdrantClient, models
from qdrant_client.conversions import common_types
from artsearch.src.services.museum_clients import (
    SMKAPIClient,
    CMAAPIClient,
    MuseumName,
)
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.utils.get_qdrant_client import get_qdrant_client
from artsearch.src.config import config


class QdrantService:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        smk_api_client: SMKAPIClient,
        cma_api_client: CMAAPIClient,
        collection_name: str,
    ):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.smk_api_client = smk_api_client
        self.cma_api_client = cma_api_client

    def _format_payload(self, payload: models.Payload | None) -> dict:
        if payload is None:
            raise ValueError("Payload cannot be None")

        if payload["production_date_start"] == payload["production_date_end"]:
            period = payload["production_date_start"]
        else:
            period = (
                f"{payload['production_date_start']} - {payload['production_date_end']}"
            )

        return {
            "title": payload["titles"][0]["title"],
            "artist": ", ".join(payload["artist"]),
            "work_types": ", ".join(
                name.capitalize() for name in payload["work_types"]
            ),
            "thumbnail_url": payload["thumbnail_url"],
            "period": period,
            "object_number": payload["object_number"],
        }

    def _format_payloads(self, payloads: list[models.Payload | None]) -> list[dict]:
        return [self._format_payload(payload) for payload in payloads]

    def _format_hit(self, hit: models.ScoredPoint) -> dict:
        formatted_hit = self._format_payload(hit.payload)
        formatted_hit.update({"score": round(hit.score, 3)})
        return formatted_hit

    def _format_hits(self, hits: list[models.ScoredPoint]) -> list[dict]:
        return [self._format_hit(hit) for hit in hits]

    def _get_vector_by_object_number(self, object_number: str) -> list[float] | None:
        """Get the vector for an object number if it exists in the collection."""
        result = self.qdrant_client.query_points(
            collection_name=self.collection_name,
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

        if not result.points or not result.points[0].vector:
            return None

        return cast(list[float], result.points[0].vector)

    def _search(
        self,
        query_vector: list[float],
        limit: int,
        offset: int,
        work_types: list[str] | None,
        museum: MuseumName,
    ) -> list[dict]:
        """Search for similar items based on a query vector."""
        conditions = []

        conditions.append(
            models.FieldCondition(
                key="museum",
                match=models.MatchValue(value=museum),
            )
        )

        if work_types is not None:
            conditions.append(
                models.FieldCondition(
                    key="work_types",
                    match=models.MatchAny(any=work_types),
                )
            )

        query_filter = models.Filter(must=conditions)
        search_params = models.SearchParams(exact=True)
        # exact=True is brute force search (ensures full recall)
        # This is slower, but okay for smaller collections
        # If speed becomes an issue, we can instead try
        # models.SearchParams(hnsw_ef=128) # Try 128, 256, or 512...
        # for a compromise between speed and recall.
        # An index on work_types would speed up
        # the payload filtering (happens before vector search),
        # but seems not to be needed yet.
        hits = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            offset=offset,
            query_filter=query_filter,
            search_params=search_params,
        )
        return self._format_hits(hits)

    def search_text(
        self,
        text_query: str,
        museum: MuseumName,
        limit: int,
        offset: int,
        work_types: list[str] | None = None,
    ) -> list[dict]:
        """Search for similar items based on a text query."""
        query_vector = get_clip_embedder().generate_text_embedding(text_query)
        return self._search(query_vector, limit, offset, work_types, museum)

    def search_similar_images(
        self,
        object_number: str,
        museum: MuseumName,
        limit: int,
        offset: int,
        work_types: list[str] | None = None,
    ) -> list[dict]:
        """Search for similar items based on an image embedding."""
        query_vector = self._get_vector_by_object_number(object_number)

        # Generate a new embedding if the object number is not found
        if query_vector is None:
            if museum == "smk":
                thumbnail_url = self.smk_api_client.get_thumbnail_url(object_number)
            elif museum == "cma":
                thumbnail_url = self.cma_api_client.get_thumbnail_url(object_number)
            query_vector = get_clip_embedder().generate_thumbnail_embedding(
                thumbnail_url, museum, object_number, cache=False
            )

        # If the object number is still not found, raise an error
        if query_vector is None:
            raise ValueError(
                "Could not generate embedding for the provided object number"
            )
        return self._search(query_vector, limit, offset, work_types, museum)

    def get_random_sample(self, museum: MuseumName, limit: int) -> list[dict]:
        """Get a random sample of items from the collection."""

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="museum",
                    match=models.MatchValue(value=museum),
                )
            ]
        )
        sampled = self.qdrant_client.query_points(
            query_filter=query_filter,
            collection_name=self.collection_name,
            query=models.SampleQuery(sample=models.Sample.RANDOM),
            with_vectors=False,
            with_payload=True,
            limit=limit,
        )
        payloads = [point.payload for point in sampled.points]
        return self._format_payloads(payloads)

    def create_qdrant_collection(self, collection_name: str, dimensions: int) -> None:
        """Create Qdrant collection (if it doesn't exist)."""
        exists = self.qdrant_client.collection_exists(collection_name=collection_name)
        if not exists:
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=dimensions, distance=models.Distance.COSINE
                ),
            )

    def upload_points(self, points: list[models.PointStruct], collection_name) -> None:
        """Upload points to a Qdrant collection."""
        self.qdrant_client.upsert(collection_name=collection_name, points=points)

    def fetch_points(
        self,
        collection_name: str,
        next_page_token,
        limit: int = 1000,
        with_vectors: bool = False,
        with_payload: bool | list[str] = True,
    ) -> tuple[list[models.Record], common_types.PointId | None]:
        """Fetch points from a Qdrant collection with pagination."""
        if collection_name is None:
            collection_name = self.collection_name

        points, next_page_token = self.qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=None,
            with_payload=with_payload,
            with_vectors=with_vectors,
            limit=limit,  # Fetch in small batches
            offset=next_page_token,  # Fetch next batch
        )

        return points, next_page_token

    def get_existing_object_numbers(
        self, collection_name: str, object_numbers: list[str], museum: MuseumName
    ) -> set[str]:
        """
        Given a list of object numbers, returns the set of object numbers from
        the list that already exist in the collection.
        """
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="object_number",
                    match=models.MatchAny(any=object_numbers),
                ),
                models.FieldCondition(
                    key="museum",
                    match=models.MatchValue(value=museum),
                ),
            ]
        )

        result = self.qdrant_client.query_points(
            collection_name=collection_name,
            query_filter=query_filter,
            limit=len(object_numbers),
            with_payload=True,
            with_vectors=False,
        )

        existing_object_numbers = set()
        for point in result.points:
            if not point.payload or "object_number" not in point.payload:
                raise ValueError(
                    f"Point {point.id} has an invalid or missing payload: {point.payload}"
                )
            existing_object_numbers.add(point.payload["object_number"])

        return existing_object_numbers


def get_qdrant_service() -> QdrantService:
    return QdrantService(
        qdrant_client=get_qdrant_client(),
        smk_api_client=SMKAPIClient(),
        cma_api_client=CMAAPIClient(),
        collection_name=config.qdrant_collection_name,
    )
