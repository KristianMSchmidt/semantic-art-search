import traceback
from typing import Any
from dataclasses import dataclass
from artsearch.src.services.qdrant_service import (
    QdrantService,
    SearchFunctionArguments,
)
from artsearch.src.services.browse_service import handle_browse
from artsearch.src.utils.get_museums import get_museum_full_name, get_museum_slugs
from artsearch.src.config import config
from artsearch.src.constants.embedding_models import (
    resolve_embedding_model,
    EmbeddingModelChoice,
)


class QueryParsingError(Exception):
    """Custom exception for errors in query parsing."""

    pass


@dataclass
class QueryAnalysisResult:
    is_find_similar_query: bool
    object_number: str | None = None
    object_museum: str | None = None
    warning_message: str | None = None


def analyze_query(
    query: str, museum_slugs: list[str] = get_museum_slugs()
) -> QueryAnalysisResult:
    """
    Checks if the query has the form {museum_slug}:{object_number}.
    """
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    if ":" in query:
        object_museum, object_number = query.split(":", 1)
        object_museum = object_museum.strip().lower()
        object_number = object_number.strip()
        if object_museum not in museum_slugs:
            raise QueryParsingError(
                f"Unknown museum: {object_museum}. Supported museums: {', '.join(museum_slugs)}."
            )
        elif not object_number:
            raise QueryParsingError("Inventory number must not be empty.")

        items = qdrant_service.get_items_by_object_number(
            object_number=object_number,
            object_museum=object_museum,
            limit=2,
        )
        if not items:
            raise QueryParsingError(
                f"No artworks found in the database from {get_museum_full_name(object_museum)} with the inventory number {object_number}."
            )
        assert len(items) == 1
        return QueryAnalysisResult(
            is_find_similar_query=True,
            object_number=object_number,
            object_museum=object_museum,
        )
    else:
        items = qdrant_service.get_items_by_object_number(
            object_number=query,
            limit=5,
            with_payload=True,
        )
        if not items:
            return QueryAnalysisResult(is_find_similar_query=False)
        elif len(items) > 1:
            example_queries = "or ".join(
                [f"`{item.payload['museum']}:{query}`" for item in items]  # type: ignore
            )
            warning_message = (
                f"Multiple artworks found in the database with the inventory number {query}. "
                f"Please make a search of the form `museum:object_number` to specify the museum (e.g. {example_queries})."
            )
            raise QueryParsingError(warning_message)
        return QueryAnalysisResult(
            is_find_similar_query=True,
            object_number=query,
        )


def handle_search(
    query: str | None,
    offset: int,
    limit: int,
    museum_prefilter: list[str] | None,
    work_type_prefilter: list[str] | None,
    total_works: int | None = None,
    museum_slugs: list[str] = get_museum_slugs(),
    embedding_model: EmbeddingModelChoice = "auto",
    seed: str | None = None,
) -> dict[Any, Any]:
    """
    Handle the search logic based on the provided query and filters.

    For browsing (no query), delegates to handle_browse which uses PostgreSQL
    for deterministic random ordering with proper pagination support.
    """
    # Browsing mode (no query) - delegate to browse handler
    if query is None or query == "":
        if seed is None:
            raise ValueError("seed is required for browsing mode (no query)")
        return handle_browse(
            offset=offset,
            limit=limit,
            museum_prefilter=museum_prefilter,
            work_type_prefilter=work_type_prefilter,
            seed=seed,
            total_works=total_works or 0,
            is_initial_load=(query is None),
        )

    # Search mode (has query)
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    header_text = None
    results = []
    error_message = None
    error_type = None

    # The user submitted a query.
    search_arguments = SearchFunctionArguments(
        query=query,
        limit=limit,
        offset=offset,
        work_type_prefilter=work_type_prefilter,
        museum_prefilter=museum_prefilter,
    )
    try:
        query_analysis = analyze_query(query, museum_slugs)

        # Resolve embedding model with context
        resolved_model = resolve_embedding_model(
            embedding_model,
            is_similarity_search=query_analysis.is_find_similar_query,
            query=query,
        )

        if query_analysis.is_find_similar_query:
            search_arguments.object_number = query_analysis.object_number
            search_arguments.object_museum = query_analysis.object_museum
            results = qdrant_service.search_similar_images(
                search_arguments, embedding_model=resolved_model
            )
        else:
            results = qdrant_service.search_text(
                search_arguments, embedding_model=resolved_model
            )
        assert total_works is not None
        works_text = f"({total_works} works)"
        header_text = (
            f"Search results {works_text}".strip() if total_works > 0 else None
        )
    except QueryParsingError as e:
        error_message = str(e)
        error_type = "warning"
    except Exception:
        traceback.print_exc()
        error_message = "An unexpected error occurred. Please try again."
        error_type = "error"

    return {
        "results": results,
        "header_text": header_text,
        "error_message": error_message,
        "error_type": error_type,
    }
