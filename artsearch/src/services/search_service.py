import logging
import traceback
from typing import Any
from dataclasses import dataclass
from django.utils.translation import gettext as _
from artsearch.src.services.qdrant_service import (
    QdrantService,
    SearchFunctionArguments,
)
from artsearch.src.services.translation_service import translate_to_english
from artsearch.src.utils.get_museums import get_museum_full_name, get_museum_slugs
from artsearch.src.config import config

logger = logging.getLogger(__name__)


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
    language: str = "en",
) -> dict[Any, Any]:
    """
    Handle the search logic based on the provided query and filters.

    Args:
        query: The search query text
        offset: Pagination offset
        limit: Number of results to return
        museum_prefilter: List of museum slugs to filter by
        work_type_prefilter: List of work types to filter by
        total_works: Total number of works matching filters
        museum_slugs: List of supported museum slugs
        language: Language code for query translation (e.g., 'en', 'da', 'nl')
    """
    qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)

    header_text = None
    results = []
    error_message = None
    error_type = None

    logger.debug(f"[SEARCH] Query: '{query}', Language: '{language}'")

    if query is None or query == "":
        if query is None:
            # Initial page load
            header_text = _("A glimpse into the archive")
        else:
            # Search with no query (currently disabled by FE)
            header_text = _("Works matching your filters")
        try:
            results = qdrant_service.get_random_sample(
                limit=limit,
                work_types=work_type_prefilter,
                museums=museum_prefilter,
            )
        except Exception:
            traceback.print_exc()
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"
    else:
        # The user submitted a query.
        # Translate query if needed (for CLIP embedding)
        # Keep original query for object number detection
        translation_result = translate_to_english(query, language)
        translated_query = translation_result.translated_text

        search_arguments = SearchFunctionArguments(
            query=translated_query,  # Use translated query for CLIP embedding
            limit=limit,
            offset=offset,
            work_type_prefilter=work_type_prefilter,
            museum_prefilter=museum_prefilter,
        )
        try:
            # Use ORIGINAL query for object number detection
            # (object numbers shouldn't be translated)
            query_analysis = analyze_query(query, museum_slugs)
            if query_analysis.is_find_similar_query:
                search_arguments.object_number = query_analysis.object_number
                search_arguments.object_museum = query_analysis.object_museum
                results = qdrant_service.search_similar_images(search_arguments)
            else:
                results = qdrant_service.search_text(search_arguments)
            assert total_works is not None
            if total_works > 0:
                header_text = _("Search results (%(count)d works)") % {
                    "count": total_works
                }
            else:
                header_text = None
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
