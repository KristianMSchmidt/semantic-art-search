from etl.pipeline.transform.transformers.smk_transformer import transform_smk_data
from etl.pipeline.transform.transformers.cma_transformer import transform_cma_data
from etl.pipeline.transform.transformers.met_transformer import transform_met_data


TRANSFORMERS = {
    "smk": transform_smk_data,
    "cma": transform_cma_data,
    "met": transform_met_data,
    # Add other museums here as they are implemented:
    # "rma": transform_rma_data,
}


def get_transformer(museum_slug: str):
    """
    Get the appropriate transformer function for a museum slug.
    
    Returns the transformer function or None if not found.
    """
    return TRANSFORMERS.get(museum_slug)