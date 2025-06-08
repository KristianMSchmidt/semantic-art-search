from dataclasses import dataclass
from typing import cast
from functools import lru_cache
from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import PointId
from artsearch.src.utils.qdrant_formatting import (
    format_payloads,
    format_hits,
)
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.utils.get_qdrant_client import get_qdrant_client
from artsearch.src.config import config


# Type aliases
TextQuery = str
TargetObjectNumber = str


@dataclass
class SearchFunctionArguments:
    """Parameters for search function"""

    query: TextQuery | TargetObjectNumber
    limit: int
    offset: int
    work_type_prefilter: list[str] | None
    museum_prefilter: list[str] | None


class QdrantService:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str,
    ):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    @lru_cache(maxsize=1)
    def _get_vector_by_object_number(self, object_number: str) -> list[float] | None:
        """Get the vector for an object number if it exists in the qdrant collection."""
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
        vector = cast(list[float], result.points[0].vector)
        return vector

    @lru_cache(maxsize=1)
    def item_exists(self, object_number: str) -> bool:
        """Check if an object number exists in the qdrant collection."""
        # Make sure this is not called every time on infinite scroll (is lru cache the right choice?)
        return self._get_vector_by_object_number(object_number) is not None

    def _search(
        self,
        query_vector: list[float],
        limit: int,
        offset: int,
        work_types: list[str] | None,
        museums: list[str] | None,
        object_number: str | None,
    ) -> list[dict]:
        """
        Perform search in qdrant collection based on vector similarity.
        If object_number is provided, it will be included in the results regardless of the other filters.
        Note that in qdrant 'should' means 'or' & 'must' means 'and'.
        """
        standard_conditions = []
        if museums is not None:
            standard_conditions.append(
                models.FieldCondition(
                    key="museum",
                    match=models.MatchAny(any=museums),
                )
            )
        if work_types is not None:
            standard_conditions.append(
                models.FieldCondition(
                    key="searchable_work_types",
                    match=models.MatchAny(any=work_types),
                )
            )

        if object_number:
            query_filter = models.Filter(
                should=[
                    # Always include this object number
                    models.Filter(
                        must=[
                            models.FieldCondition(
                                key="object_number",
                                match=models.MatchValue(value=object_number),
                            )
                        ]
                    ),
                    # Or match the standard conditions
                    models.Filter(must=standard_conditions),
                ]
            )
        else:
            query_filter = models.Filter(must=standard_conditions)

        # exact=True is brute force search (ensures full recall)
        # This is slower, but okay for smaller collections
        # If speed becomes an issue, we can instead try
        # models.SearchParams(hnsw_ef=128) # Try 128, 256, or 512...
        # for a compromise between speed and recall.
        # An index on work_types would speed up
        # the payload filtering (happens before vector search),
        # but seems not to be needed yet.
        search_params = models.SearchParams(exact=True)

        hits = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            offset=offset,
            query_filter=query_filter,
            search_params=search_params,
        )

        return format_hits(hits)

    def search_text(self, search_function_args: SearchFunctionArguments) -> list[dict]:
        """Search for related artworks based on a text query."""
        # Unpack the search function arguments
        query: TextQuery = search_function_args.query
        limit = search_function_args.limit
        offset = search_function_args.offset
        work_types = search_function_args.work_type_prefilter
        museums = search_function_args.museum_prefilter
        query_vector = get_clip_embedder().generate_text_embedding(query)
        return self._search(
            query_vector, limit, offset, work_types, museums, object_number=None
        )

    def search_similar_images(
        self,
        search_function_args: SearchFunctionArguments,
    ) -> list[dict]:
        """
        Search for artworks similar to the given target object based on vector embedding similarity.
        """
        # Unpack the search function arguments
        object_number: TargetObjectNumber = search_function_args.query
        limit = search_function_args.limit
        offset = search_function_args.offset
        work_types = search_function_args.work_type_prefilter
        museums = search_function_args.museum_prefilter

        # Fetch vector and paylod of target object from Qdrant collection (if object exists in collection)
        query_vector = self._get_vector_by_object_number(object_number)
        print("HELLO FROM SEARCH SIMILAR IMAGES")
        print(object_number)
        print("offset", offset)
        print(museums)
        print(work_types)
        # If the embedding could not be generated, raise an error
        if query_vector is None:
            raise ValueError("No vector found for the given object number. ")
        return self._search(
            query_vector, limit, offset, work_types, museums, object_number
        )

    def get_random_sample(
        self, limit: int, work_types: list[str] | None, museums: list[str] | None
    ) -> list[dict]:
        """Get a random sample of items from the collection."""
        conditions = []
        if museums is not None:
            conditions.append(
                models.FieldCondition(
                    key="museum",
                    match=models.MatchAny(any=museums),
                )
            )
        if work_types is not None:
            conditions.append(
                models.FieldCondition(
                    key="searchable_work_types",
                    match=models.MatchAny(any=work_types),
                )
            )

        sampled = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=models.SampleQuery(sample=models.Sample.RANDOM),
            with_vectors=False,
            with_payload=True,
            limit=limit,
            query_filter=models.Filter(must=conditions),
        )
        payloads = [point.payload for point in sampled.points]
        return format_payloads(payloads)

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
        next_page_token: PointId | None,
        limit: int = 1000,
        with_vectors: bool = False,
        with_payload: bool | list[str] = True,
    ) -> tuple[list[models.Record], PointId | None]:
        """Fetch points from a Qdrant collection with pagination."""

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
        self, collection_name: str, object_numbers: list[str], museum: str
    ) -> set[str]:
        """
        Given a list of object numbers, returns the set of object numbers from
        the list that already exist in the collection.
        """
        if not object_numbers:
            return set()
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
        collection_name=config.qdrant_collection_name,
    )
