from etl.pipeline.transform.transformers.smk_transformer import transform_smk_data


TRANSFORMERS = {
    "smk": transform_smk_data,
    # Add other museums here as they are implemented:
    # "cma": transform_cma_data,
    # "rma": transform_rma_data,
    # "met": transform_met_data,
}


def get_transformer(museum_slug: str):
    """
    Get the appropriate transformer function for a museum slug.
    
    Returns the transformer function or None if not found.
    """
    return TRANSFORMERS.get(museum_slug)