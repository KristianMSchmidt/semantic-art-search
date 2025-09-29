from typing import Optional
from etl.pipeline.transform.transformers.smk_transformer import SmkTransformer
from etl.pipeline.transform.transformers.cma_transformer import CmaTransformer
from etl.pipeline.transform.transformers.met_transformer import MetTransformer
from etl.pipeline.transform.transformers.rma_transformer import RmaTransformer
from etl.pipeline.transform.base_transformer import BaseTransformer

TRANSFORMERS: dict[str, BaseTransformer] = {
    "smk": SmkTransformer(),
    "cma": CmaTransformer(),
    "rma": RmaTransformer(),
    "met": MetTransformer(),
}


def get_transformer(museum_slug: str) -> Optional[BaseTransformer]:
    """
    Get the appropriate transformer instance for a museum slug.

    Returns the transformer instance or None if not found.
    """
    return TRANSFORMERS.get(museum_slug)
