from typing import Callable
from artsearch.src.utils.get_museums import get_museum_slugs
from etl.pipeline.extract.extractors.smk_extractor import store_raw_data_smk
from etl.pipeline.extract.extractors.cma_extractor import store_raw_data_cma
from etl.pipeline.extract.extractors.met_extractor import store_raw_data_met
from etl.pipeline.extract.extractors.rma_extractor import store_raw_data_rma


EXTRACTORS = {
    "smk": store_raw_data_smk,
    "cma": store_raw_data_cma,
    "met": store_raw_data_met,
    "rma": store_raw_data_rma,
}


def get_extractor(museum_slug: str) -> Callable:
    """
    Get the appropriate extractor function for a museum slug.

    Returns the extractor function or raises ValueError if not found.
    """
    # Validate that the museum_slug is supported
    supported_slugs = get_museum_slugs()
    if museum_slug not in supported_slugs:
        raise ValueError(f"Unsupported museum slug: {museum_slug}. Supported: {supported_slugs}")
    
    extractor = EXTRACTORS.get(museum_slug)
    if extractor is None:
        raise ValueError(f"No extractor implementation found for museum slug: {museum_slug}")
    return extractor
