# Backward compatibility import - EmbeddingLoadService has moved to etl.services
# This import will be deprecated in future versions
import warnings
from etl.services.embedding_load_service import EmbeddingLoadService

warnings.warn(
    "Importing EmbeddingLoadService from etl.pipeline.load.load_embeddings.service is deprecated. "
    "Use 'from etl.services.embedding_load_service import EmbeddingLoadService' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = ['EmbeddingLoadService']
