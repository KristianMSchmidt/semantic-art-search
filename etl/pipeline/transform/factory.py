from typing import Callable
from etl.pipeline.transform.transformers.smk_transformer import transform_smk_data
from etl.pipeline.transform.transformers.cma_transformer import transform_cma_data
from etl.pipeline.transform.transformers.met_transformer import transform_met_data
from etl.pipeline.transform.transformers.rma_transformer import transform_rma_data


TRANSFORMERS = {
    "smk": transform_smk_data,
    "cma": transform_cma_data,
    "met": transform_met_data,
    "rma": transform_rma_data,
    # Add other museums here as they are implemented:
}


def get_transformer(museum_slug: str) -> Callable:
    """
    Get the appropriate transformer function for a museum slug.

    Returns the transformer function or None if not found.
    """
    return TRANSFORMERS[museum_slug]
