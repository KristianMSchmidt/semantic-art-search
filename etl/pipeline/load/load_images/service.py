# Backward compatibility import - ImageLoadService has moved to etl.services
# This import will be deprecated in future versions
import warnings
from etl.services.image_load_service import ImageLoadService

warnings.warn(
    "Importing ImageLoadService from etl.pipeline.load.load_images.service is deprecated. "
    "Use 'from etl.services.image_load_service import ImageLoadService' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = ['ImageLoadService']