import traceback
from typing import Iterable, TypedDict
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


class SearchResult(TypedDict):
    results: list
    header_text: str | None
    error_message: str | None
    error_type: str | None
    total_works: int


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


def _execute_query_search(
    query: str,
    offset: int,
    limit: int,
    museum_prefilter: list[str] | None,
    work_type_prefilter: list[str] | None,
    all_museum_slugs: list[str],
    embedding_model: EmbeddingModelChoice,
) -> list:
    """Execute a text or similarity search for the given query."""
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    query_analysis = analyze_query(query, all_museum_slugs)

    resolved_model = resolve_embedding_model(
        embedding_model,
        is_similarity_search=query_analysis.is_find_similar_query,
        query=query,
    )

    search_arguments = SearchFunctionArguments(
        query=query,
        limit=limit,
        offset=offset,
        work_type_prefilter=work_type_prefilter,
        museum_prefilter=museum_prefilter,
        object_number=query_analysis.object_number,
        object_museum=query_analysis.object_museum,
    )

    if query_analysis.is_find_similar_query:
        return qdrant_service.search_similar_images(
            search_arguments, embedding_model=resolved_model
        )
    return qdrant_service.search_text(
        search_arguments, embedding_model=resolved_model
    )


def handle_search(
    query: str | None,
    offset: int,
    limit: int,
    museums: list[str] | None = None,
    work_types: list[str] | None = None,
    embedding_model: EmbeddingModelChoice = "auto",
    seed: str | None = None,
) -> SearchResult:
    """
    Handle the search logic based on the provided query and filters.

    For browsing (no query), delegates to handle_browse which uses PostgreSQL
    for deterministic random ordering with proper pagination support.
    """
    all_museum_slugs = get_museum_slugs()
    all_work_type_names = get_work_type_names()
    selected_museums = museums if museums else all_museum_slugs
    selected_work_types = work_types if work_types else all_work_type_names

    museum_prefilter = make_prefilter(all_museum_slugs, selected_museums)
    work_type_prefilter = make_prefilter(all_work_type_names, selected_work_types)

    total_works = get_total_works_for_filters(
        tuple(selected_museums),
        tuple(selected_work_types),
    )

    if query is None or query == "":
        if seed is None:
            raise ValueError("seed is required for browsing mode (no query)")
        return handle_browse(
            offset=offset,
            limit=limit,
            museum_prefilter=museum_prefilter,
            work_type_prefilter=work_type_prefilter,
            seed=seed,
            total_works=total_works,
            is_initial_load=(query is None),
        )

    try:
        results = _execute_query_search(
            query=query,
            offset=offset,
            limit=limit,
            museum_prefilter=museum_prefilter,
            work_type_prefilter=work_type_prefilter,
            all_museum_slugs=all_museum_slugs,
            embedding_model=embedding_model,
        )
        header_text = (
            f"Search results ({total_works} works)" if total_works > 0 else None
        )
        return SearchResult(
            results=results,
            header_text=header_text,
            error_message=None,
            error_type=None,
            total_works=total_works,
        )
    except QueryParsingError as e:
        return SearchResult(
            results=[],
            header_text=None,
            error_message=str(e),
            error_type="warning",
            total_works=total_works,
        )
    except Exception:
        traceback.print_exc()
        return SearchResult(
            results=[],
            header_text=None,
            error_message="An unexpected error occurred. Please try again.",
            error_type="error",
            total_works=total_works,
        )
