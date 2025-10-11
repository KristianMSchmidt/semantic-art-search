from dataclasses import dataclass
from typing import cast, Any
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
    object_number: str | None = None
    object_museum: str | None = None


class QdrantService:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str,
    ):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    @lru_cache(maxsize=10)
    def get_items_by_object_number(
        self,
        object_number: str,
        object_museum: str | None = None,
        with_vector: bool = False,
        with_payload: bool | list[str] = False,
        limit: int = 1,
    ) -> list[models.ScoredPoint]:
        """
        Get items by object number.
        If museum is provided, it will filter by museum as well.
        """
        conditions = []

        conditions.append(
            models.FieldCondition(
                key="object_number", match=models.MatchValue(value=object_number)
            )
        )

        if object_museum is not None:
            conditions.append(
                models.FieldCondition(
                    key="museum", match=models.MatchValue(value=object_museum)
                )
            )

        result = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query_filter=models.Filter(must=conditions),
            with_payload=with_payload,
            with_vectors=with_vector,
            limit=limit,
        )
        return result.points

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

        response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            offset=offset,
            query_filter=query_filter,
            search_params=search_params,
            using="image_clip",
        )

        return format_hits(response.points)

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
        limit = search_function_args.limit
        offset = search_function_args.offset
        work_types = search_function_args.work_type_prefilter
        museums = search_function_args.museum_prefilter

        object_number = search_function_args.object_number
        object_museum = search_function_args.object_museum

        # Fetch vector target object from Qdrant collection
        items = self.get_items_by_object_number(
            object_number=object_number,
            object_museum=object_museum,
            with_vector=True,
            limit=1,
        )
        if not items or items[0].vector is None:
            raise ValueError("No vector found for the given object number and museum.")
        vec = items[0].vector
        # Qdrant may return either a single vector (list[float]) or a dict of named vectors.
        if isinstance(vec, dict):
            named_vecs = cast(dict[str, list[float]], vec)
            image_clip_vec = named_vecs.get("image_clip")
            if image_clip_vec is None:
                raise ValueError(
                    "No 'image_clip' vector found in the point's named vectors."
                )
            query_vector = cast(list[float], image_clip_vec)
        else:
            query_vector = cast(list[float], vec)

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

    def get_existing_values(
        self,
        values: list[Any],
        museum: str,
        id_key: str = "object_number",
        collection_name: str = config.qdrant_collection_name_etl,
    ) -> set[str]:
        """
        Given a qdrant collection key, a museum name and list of values,
        returns the subset of these values that already exist in the collection for the given museum.
        """
        if not values:
            return set()

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key=id_key,
                    match=models.MatchAny(any=values),
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
            with_payload=True,
            with_vectors=False,
            limit=len(values),  # We want to fetch all points that match the values
        )
        existing_object_numbers = set()
        for point in result.points:
            if not point.payload or id_key not in point.payload:
                raise ValueError(
                    f"Point {point.id} has an invalid or missing payload: {point.payload}"
                )
            existing_object_numbers.add(point.payload[id_key])

        return existing_object_numbers


def get_qdrant_service() -> QdrantService:
    return QdrantService(
        qdrant_client=get_qdrant_client(),
        collection_name=config.qdrant_collection_name_app,
    )
