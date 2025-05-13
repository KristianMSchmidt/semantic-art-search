from dataclasses import dataclass
from typing import cast
from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import PointId
from artsearch.src.services.museum_clients.base_client import MuseumName
from artsearch.src.utils.get_metadata_and_museum import get_metadata_and_museum
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
    museum_filter: MuseumName
    limit: int
    offset: int
    work_types_prefilter: list[str] | None


class QdrantService:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str,
    ):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

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

    def _search(
        self,
        query_vector: list[float],
        limit: int,
        offset: int,
        work_types: list[str] | None,
        museum_filter: MuseumName,
        object_number: str | None,
    ) -> list[dict]:
        """
        Perform search in qdrant collection based on vector similarity.
        If object_number is provided, it will be included in the results regardless of the other filters.
        Note that in qdrant 'should' means 'or' & 'must' means 'and'.
        """
        standard_conditions = []
        if museum_filter != "all":
            standard_conditions.append(
                models.FieldCondition(
                    key="museum",
                    match=models.MatchValue(value=museum_filter),
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
        museum_filter = search_function_args.museum_filter
        limit = search_function_args.limit
        offset = search_function_args.offset
        work_types = search_function_args.work_types_prefilter

        query_vector = get_clip_embedder().generate_text_embedding(query)
        return self._search(
            query_vector, limit, offset, work_types, museum_filter, object_number=None
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
        museum_filter = search_function_args.museum_filter
        limit = search_function_args.limit
        offset = search_function_args.offset
        work_types = search_function_args.work_types_prefilter

        # Fetch vector and paylod of target object from Qdrant collection (if object exists in collection)
        query_vector = self._get_vector_by_object_number(object_number)

        if query_vector is None:
            # If the vector does not exist already, try to generate it from the thumbnail URL
            thumbnail_url, object_museum = get_metadata_and_museum(
                object_number, museum_filter
            )
            query_vector = get_clip_embedder().generate_thumbnail_embedding(
                thumbnail_url, object_museum, object_number, cache=False
            )

        # If the embedding could not be generated, raise an error
        if query_vector is None:
            raise ValueError(
                "Could not generate embedding for the provided object number"
            )
        return self._search(
            query_vector, limit, offset, work_types, museum_filter, object_number
        )

    def get_random_sample(self, museum_filter: MuseumName, limit: int) -> list[dict]:
        """Get a random sample of items from the collection."""
        if museum_filter == "all":
            query_filter = None
        else:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="museum",
                        match=models.MatchValue(value=museum_filter),
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
        self, collection_name: str, object_numbers: list[str], museum: MuseumName
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
