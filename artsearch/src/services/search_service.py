import traceback
from typing import Any, Iterable
from dataclasses import dataclass
from artsearch.src.services.qdrant_service import (
    QdrantService,
    SearchFunctionArguments,
)
from artsearch.src.services.browse_service import handle_browse
from artsearch.src.services.museum_stats_service import (
    get_total_works_for_filters,
    get_work_type_names,
)
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


def make_prefilter(
    all_items: Iterable[str],
    selected_items: list[str],
) -> list[str] | None:
    """
    Generalized prefilter function for work types and museums.
    If all items are selected, or none are selected, return None.
    """
    if not selected_items or len(selected_items) == len(list(all_items)):
        return None
    return selected_items


def handle_search(
    query: str | None,
    offset: int,
    limit: int,
    museums: list[str] | None = None,
    work_types: list[str] | None = None,
    embedding_model: EmbeddingModelChoice = "auto",
    seed: str | None = None,
) -> dict[Any, Any]:
    """
    Handle the search logic based on the provided query and filters.

    Args:
        museums: Selected museum slugs, or None for all museums.
        work_types: Selected work types, or None for all work types.

    For browsing (no query), delegates to handle_browse which uses PostgreSQL
    for deterministic random ordering with proper pagination support.
    """
    # Resolve None → all items
    all_museum_slugs = get_museum_slugs()
    all_work_type_names = get_work_type_names()
    selected_museums = museums if museums else all_museum_slugs
    selected_work_types = work_types if work_types else all_work_type_names

    # Build prefilters (None means "all selected")
    museum_prefilter = make_prefilter(all_museum_slugs, selected_museums)
    work_type_prefilter = make_prefilter(all_work_type_names, selected_work_types)

    # Compute total works for the current filters
    total_works = get_total_works_for_filters(
        tuple(selected_museums),
        tuple(selected_work_types),
    )

    # Browsing mode (no query) - delegate to browse handler
    if query is None or query == "":
        if seed is None:
            raise ValueError("seed is required for browsing mode (no query)")
        browse_result = handle_browse(
            offset=offset,
            limit=limit,
            museum_prefilter=museum_prefilter,
            work_type_prefilter=work_type_prefilter,
            seed=seed,
            total_works=total_works,
            is_initial_load=(query is None),
        )
        return {**browse_result, "total_works": total_works}

    # Search mode (has query)
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    header_text = None
    results = []
    error_message = None
    error_type = None

    search_arguments = SearchFunctionArguments(
        query=query,
        limit=limit,
        offset=offset,
        work_type_prefilter=work_type_prefilter,
        museum_prefilter=museum_prefilter,
    )
    try:
        query_analysis = analyze_query(query, all_museum_slugs)

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
        "total_works": total_works,
    }
