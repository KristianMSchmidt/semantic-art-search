from typing import Callable
from functools import partial
from artsearch.src.utils.get_museums import get_museum_slugs
from etl.pipeline.extract.extractors.smk_extractor import store_raw_data_smk
from etl.pipeline.extract.extractors.cma_extractor import store_raw_data_cma
from etl.pipeline.extract.extractors.met_extractor import store_raw_data_met
from etl.pipeline.extract.extractors.rma_extractor import store_raw_data_rma
from etl.pipeline.extract.extractors.aic_extractor import store_raw_data_aic


EXTRACTORS = {
    "smk": store_raw_data_smk,
    "cma": store_raw_data_cma,
    "met": store_raw_data_met,
    "rma": store_raw_data_rma,
    "aic": store_raw_data_aic,
}


def get_extractor(museum_slug: str, force_refetch: bool = False) -> Callable:
    """
    Get the appropriate extractor function for a museum slug.

    Args:
        museum_slug: The museum identifier (smk, cma, met, rma)
        force_refetch: Whether to force refetch all items regardless of existing data

    Returns the extractor function with force_refetch parameter bound, or raises ValueError if not found.
    """
    # Validate that the museum_slug is supported
    supported_slugs = get_museum_slugs()
    if museum_slug not in supported_slugs:
        raise ValueError(
            f"Unsupported museum slug: {museum_slug}. Supported: {supported_slugs}"
        )

    extractor = EXTRACTORS.get(museum_slug)
    if extractor is None:
        raise ValueError(
            f"No extractor implementation found for museum slug: {museum_slug}"
        )

    # Return a partial function with force_refetch parameter bound
    return partial(extractor, force_refetch=force_refetch)
