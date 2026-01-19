# Architectural Separation: ETL vs App

## Two Distinct Components

1. **artsearch app** (`artsearch/`): User-facing search application
   - Search service and views
   - Museum client utilities (for generating object URLs)
   - Frontend formatting utilities
   - Django admin customizations

2. **ETL pipeline** (`etl/`): Data processing infrastructure
   - Extract: Bulk data fetching from museum APIs
   - Transform: Data standardization and validation
   - Load: Image storage and embedding generation
   - Django models for raw and transformed data

## Design Principle: Keep ETL and App Separate

**Why**: The ETL pipeline may be split into a separate repository. Clear boundaries now make this easier later.

**How**:
- **Avoid creating new cross-dependencies** between `etl/` and `artsearch/`
- **Accept intentional duplication** when it represents genuine architectural independence
  - Example: Museum API URLs defined in both extractors and museum clients serve different purposes
  - Extractors: Bulk data collection (search endpoints, pagination)
  - Museum clients: Individual object URL construction (single item lookups)

## Known Coupling Points

Current dependencies between ETL and artsearch:

1. **`get_bucket_image_url()`** from `etl/services/bucket_service.py`
   - Used by: ETL image loader + artsearch frontend formatting
   - Reason: Both need S3 URLs for thumbnails

2. **Museum client utilities** from `artsearch/src/services/museum_clients/utils.py`
   - Used by: ETL models (admin links) + artsearch frontend formatting
   - Reason: Both need museum page/API URLs for objects

3. **`get_qdrant_service()`** from `artsearch/src/services/qdrant_service.py`
   - Used by: ETL embedding loader + artsearch search service
   - Reason: Both interact with Qdrant (ETL writes, app reads)

**Future split strategy**: Extract to shared package, duplicate, or leave as dependency.

**Current stance**: Don't solve prematurely. Coupling is documented and minimal.
