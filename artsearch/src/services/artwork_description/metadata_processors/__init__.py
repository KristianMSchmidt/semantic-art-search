"""Museum-specific metadata processors."""

from .smk import clean_smk_metadata
from .cma import clean_cma_metadata
from .met import clean_met_metadata
from .rma import clean_rma_metadata
from .aic import clean_aic_metadata
from .nga import clean_nga_metadata

__all__ = [
    "clean_smk_metadata",
    "clean_cma_metadata",
    "clean_met_metadata",
    "clean_rma_metadata",
    "clean_aic_metadata",
    "clean_nga_metadata",
]
