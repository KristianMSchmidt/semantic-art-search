# Backward compatibility import - BucketService has moved to etl.services
# This import will be deprecated in future versions
import warnings
from etl.services.bucket_service import BucketService, get_bucket_image_key, get_bucket_image_url

warnings.warn(
    "Importing BucketService from artsearch.src.services.bucket_service is deprecated. "
    "Use 'from etl.services.bucket_service import BucketService' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = ['BucketService', 'get_bucket_image_key', 'get_bucket_image_url']