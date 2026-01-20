from dataclasses import dataclass
from typing import cast
from functools import lru_cache
import time
import logging
from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import PointId
from artsearch.src.utils.qdrant_formatting import (
    format_payloads,
    format_hits,
)
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.jina_embedder import get_jina_embedder
from artsearch.src.utils.get_qdrant_client import get_qdrant_client
from artsearch.src.config import config
from artsearch.src.constants.embedding_models import (
    MODEL_TO_VECTOR_NAME,
    ResolvedEmbeddingModel,
)

logger = logging.getLogger(__name__)


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
        collection_name: str,
        qdrant_client: QdrantClient | None = None,
    ):
        self.qdrant_client = qdrant_client or get_qdrant_client()
        self.collection_name = collection_name

    def get_items_by_object_number(
        self,
        object_number: str,
        object_museum: str | None = None,
        with_vector: bool = False,
        with_payload: bool = False,
        limit: int = 1,
    ) -> list[models.ScoredPoint]:
        """
        Get items by object number.
        If museum is provided, it will filter by museum as well.
        """
        return _get_items_by_object_number_cached(
            object_number=object_number,
            object_museum=object_museum,
            with_vector=with_vector,
            with_payload=with_payload,
            limit=limit,
            collection_name=self.collection_name,
        )

    def _search(
        self,
        query_vector: list[float],
        limit: int,
        offset: int,
        work_types: list[str] | None,
        museums: list[str] | None,
        object_number: str | None,
        embedding_model: ResolvedEmbeddingModel = "clip",
    ) -> list[dict]:
        """
        Perform search in qdrant collection based on vector similarity.
        If object_number is provided, it will be included in the results regardless of the other filters.
        Note that in qdrant 'should' means 'or' & 'must' means 'and'.
        """
        start_time = time.time()

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

        # Determine which vector to search based on embedding model
        vector_name = MODEL_TO_VECTOR_NAME[embedding_model]

        qdrant_start = time.time()
        response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            offset=offset,
            query_filter=query_filter,
            search_params=search_params,
            using=vector_name,
        )
        qdrant_time = (time.time() - qdrant_start) * 1000

        logger.info(
            f"[TIMING] Qdrant vector search - "
            f"limit={limit}, offset={offset}, "
            f"museums={museums}, work_types={work_types}, "
            f"object_number={object_number}, "
            f"exact_search=True: {qdrant_time:.2f}ms"
        )

        format_start = time.time()
        formatted = format_hits(response.points)
        format_time = (time.time() - format_start) * 1000

        total_time = (time.time() - start_time) * 1000
        logger.info(
            f"[TIMING] _search total: {total_time:.2f}ms "
            f"(qdrant: {qdrant_time:.2f}ms, format: {format_time:.2f}ms)"
        )

        return formatted

    def search_text(
        self,
        search_function_args: SearchFunctionArguments,
        embedding_model: ResolvedEmbeddingModel = "clip",
    ) -> tuple[list[dict], ResolvedEmbeddingModel]:
        """Search for related artworks based on a text query.

        Returns:
            Tuple of (results, actual_model_used). The actual model may differ
            from the requested model if a fallback occurred (e.g., Jina → CLIP).
        """

        # Unpack the search function arguments
        query: TextQuery = search_function_args.query
        limit = search_function_args.limit
        offset = search_function_args.offset
        work_types = search_function_args.work_type_prefilter
        museums = search_function_args.museum_prefilter

        # Choose embedder based on model
        actual_model = embedding_model
        embedding_start = time.time()
        if embedding_model == "jina":
            try:
                query_vector = get_jina_embedder().generate_text_embedding(query)
            except Exception as e:
                logger.warning(f"Jina embedding failed, falling back to CLIP: {e}")
                query_vector = get_clip_embedder().generate_text_embedding(query)
                actual_model = "clip"  # Update for correct Qdrant collection
        else:
            query_vector = get_clip_embedder().generate_text_embedding(query)
        embedding_time = (time.time() - embedding_start) * 1000

        logger.info(
            f"[TIMING] search_text - {actual_model.upper()} text embedding: {embedding_time:.2f}ms"
        )

        results = self._search(
            query_vector,
            limit,
            offset,
            work_types,
            museums,
            object_number=None,
            embedding_model=actual_model,
        )

        return results, actual_model

    def search_similar_images(
        self,
        search_function_args: SearchFunctionArguments,
        embedding_model: ResolvedEmbeddingModel = "clip",
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
        start_time = time.time()
        assert object_number is not None, (
            "object_number must be provided for similarity search."
        )
        items = self.get_items_by_object_number(
            object_number=object_number,
            object_museum=object_museum,
            with_vector=True,
            limit=1,
        )
        logger.info(
            f"[TIMING] search_similar_images - fetch target object from Qdrant: "
            f"{(time.time() - start_time) * 1000:.2f}ms"
        )

        if not items or items[0].vector is None:
            raise ValueError("No vector found for the given object number and museum.")
        vec = items[0].vector

        # Determine which vector name to use based on embedding model
        vector_name = MODEL_TO_VECTOR_NAME[embedding_model]

        # Qdrant may return either a single vector (list[float]) or a dict of named vectors.
        if isinstance(vec, dict):
            named_vecs = cast(dict[str, list[float]], vec)
            target_vec = named_vecs.get(vector_name)
            if target_vec is None:
                raise ValueError(
                    f"No '{vector_name}' vector found in the point's named vectors."
                )
            query_vector = cast(list[float], target_vec)
        else:
            query_vector = cast(list[float], vec)

        results = self._search(
            query_vector,
            limit,
            offset,
            work_types,
            museums,
            object_number,
            embedding_model=embedding_model,
        )

        return results

    def get_items_by_ids(
        self,
        artwork_ids: list[tuple[str, str]],  # (museum_slug, object_number)
    ) -> list[dict]:
        """
        Fetch full payloads for multiple artworks by their (museum, object_number) pairs.

        Since object_numbers are only unique per museum, we use compound filters.
        Results are returned in the same order as the input artwork_ids.

        Args:
            artwork_ids: List of (museum_slug, object_number) tuples

        Returns:
            List of formatted payloads in the same order as input
        """
        if not artwork_ids:
            return []

        start_time = time.time()

        # Build compound filter: (museum=A AND obj=1) OR (museum=B AND obj=2) OR ...
        should_conditions = [
            models.Filter(
                must=[
                    models.FieldCondition(
                        key="museum", match=models.MatchValue(value=museum)
                    ),
                    models.FieldCondition(
                        key="object_number", match=models.MatchValue(value=obj_num)
                    ),
                ]
            )
            for museum, obj_num in artwork_ids
        ]

        result = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query_filter=models.Filter(should=should_conditions),
            with_payload=True,
            limit=len(artwork_ids),
        )

        qdrant_time = (time.time() - start_time) * 1000

        # Build lookup dict for reordering
        payload_map = {
            (p.payload["museum"], p.payload["object_number"]): p.payload
            for p in result.points
        }

        # Return in original order from PostgreSQL
        ordered_payloads = [
            payload_map[key] for key in artwork_ids if key in payload_map
        ]

        format_start = time.time()
        formatted = format_payloads(ordered_payloads)
        format_time = (time.time() - format_start) * 1000

        logger.info(
            f"[TIMING] get_items_by_ids - "
            f"requested={len(artwork_ids)}, found={len(ordered_payloads)}, "
            f"qdrant={qdrant_time:.2f}ms, format={format_time:.2f}ms"
        )

        return formatted

    def upload_points(self, points: list[models.PointStruct]) -> None:
        """Upload points to a Qdrant collection."""
        self.qdrant_client.upsert(collection_name=self.collection_name, points=points)

    def get_point_vectors(self, point_id: str) -> dict[str, list[float]] | None:
        """Fetch existing vectors for a point. Returns None if point doesn't exist."""
        try:
            points = self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_vectors=True,
            )
            if points and points[0].vector:
                return cast(dict[str, list[float]], points[0].vector)
            return None
        except Exception:
            return None

    def fetch_points(
        self,
        next_page_token: PointId | None,
        limit: int = 1000,
        with_vectors: bool = False,
        with_payload: bool | list[str] = True,
    ) -> tuple[list[models.Record], PointId | None]:
        """Fetch points from a Qdrant collection with pagination."""

        points, next_page_token = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=None,
            with_payload=with_payload,
            with_vectors=with_vectors,
            limit=limit,  # Fetch in small batches
            offset=next_page_token,  # Fetch next batch
        )

        return points, next_page_token


@lru_cache(maxsize=128)
def _get_items_by_object_number_cached(
    object_number: str,
    object_museum: str | None = None,
    with_vector: bool = False,
    with_payload: bool = False,
    limit: int = 1,
    collection_name: str = config.qdrant_collection_name_app,
) -> list[models.ScoredPoint]:
    """
    Private cached function to fetch items by object number from Qdrant.

    Returns list of ScoredPoint objects matching the object_number filter.
    If object_museum is provided, also filters by museum.

    Results are cached based on all parameters.
    Called by QdrantService.get_items_by_object_number() instance method.
    """
    qdrant_client = get_qdrant_client()
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

    result = qdrant_client.query_points(
        collection_name=collection_name,
        query_filter=models.Filter(must=conditions),
        with_payload=with_payload,
        with_vectors=with_vector,
        limit=limit,
    )
    return list(result.points)
