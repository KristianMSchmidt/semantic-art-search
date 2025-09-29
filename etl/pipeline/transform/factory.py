from typing import Optional
from etl.pipeline.transform.transformers.smk_transformer import transform_smk_data
from etl.pipeline.transform.transformers.cma_transformer import transform_cma_data
from etl.pipeline.transform.transformers.met_transformer import transform_met_data
from etl.pipeline.transform.transformers.rma_transformer import transform_rma_data
from etl.pipeline.transform.models import TransformerFn

TRANSFORMERS: dict[str, TransformerFn] = {
    "smk": transform_smk_data,
    "cma": transform_cma_data,
    "rma": transform_rma_data,
    "met": transform_met_data,
}


def get_transformer(museum_slug: str) -> Optional[TransformerFn]:
    """
    Get the appropriate transformer function for a museum slug.

    Returns the transformer function or None if not found.
    """
    return TRANSFORMERS.get(museum_slug)
