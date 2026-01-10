# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Semantic Art Search is a Django-based web application that uses CLIP (Contrastive Language-Image Pre-training) to enable semantic search of artwork collections from multiple museums. The system allows users to search artworks using natural language queries and find visually or thematically similar pieces.

### Core Applications
- **artsearch**: Main Django app containing search functionality, models, services, and views
- **etl**: Extract, Transform, Load app for processing museum data
- **theme**: Tailwind CSS theme configuration
- **djangoconfig**: Django project configuration

### Data Flow
1. **ETL Pipeline**: Museum APIs → Raw metadata (PostgreSQL) → Transformed data → Images (S3) → Embeddings (Qdrant)
2. **Search Pipeline**: User query → CLIP text embedding → Qdrant vector search → Results
3. **Similar Image Search**: Object number → Retrieve image embedding → Vector similarity search

### Museum Integration
The system integrates with four major museums through their open APIs:
- **SMK**: Statens Museum for Kunst (Denmark)
- **CMA**: Cleveland Museum of Art
- **RMA**: Rijksmuseum Amsterdam
- **MET**: Metropolitan Museum of Art

Each museum has a dedicated client in `artsearch/src/services/museum_clients/`

**Core Design Principle - Unique Public Identifiers:**
This project requires **unique public artwork identifiers** for every museum. These identifiers must be:
- **Public-facing**: Searchable and recognizable to users (accession numbers, not internal IDs)
- **Unique**: Each identifier maps to exactly one artwork in the system
- **Enforced**: If museums don't provide unique public identifiers, the system makes them unique

This principle drives the duplicate detection logic in MET and RMA extractors. When duplicate public identifiers are encountered, the system uses a "first occurrence wins" strategy to maintain data integrity throughout the ETL pipeline.

**MET API Data Model:**
- `objectID`: Internal database ID, true unique identifier (used in MET's URLs)
- `accessionNumber`: Public catalog number, **NOT guaranteed unique** (~0.3% duplicates in dataset)
- MET's own website uses `objectID` in URLs, not accession numbers
- **System choice**: Uses `object_number` (accessionNumber) as unique key for better UX
- **Duplicate handling**: MET extractor detects and skips artworks with duplicate accession numbers (first occurrence wins)
- **Trade-off**: Accepts ~0.3% data loss for searchability and data integrity (users search by accession numbers, not internal IDs)

**RMA API Data Model:**
- RMA uses complex nested OAI-PMH XML/RDF structure for metadata
- `item_id`: API identifier from the collection search endpoint
- `object_number`: Extracted from `dc:identifier` in the RDF metadata (public identifier, not guaranteed unique by design)
- **Duplicate handling**: RMA extractor detects and skips artworks with duplicate object_numbers
- **System choice**: Uses `object_number` as unique key for searchability (same as MET)
- **First occurrence wins**: Once an object_number is stored, duplicates with different museum_db_ids are skipped
- **Current status**: No duplicates observed in practice yet, but safeguard prevents data corruption if they exist

## Development Setup

### Environment Configuration
- **artsearch/src/config.py**: Environment-based configuration using Pydantic
- Requires `.env.dev` or `.env.prod` files for environment variables
- Key dependencies: Qdrant, PostgreSQL, Linode Object Storage (S3-compatible), CLIP model

**Required environment variables:**
- Database: `POSTGRES_*` variables
- Vector DB: `QDRANT_URL`, `QDRANT_API_KEY`
- Storage: `AWS_*` variables for S3-compatible object storage
- Django: `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG`

### Docker Deployment
- **Development**: `docker-compose.dev.yml` - includes local PostgreSQL database and web container
- **Production**: `docker-compose.prod.yml` - web container only (uses cloud PostgreSQL), includes nginx reverse proxy
- Production commands use `make prod_*` prefix

### Makefile Organization

The project uses a split Makefile structure for better organization:

**Main Makefile:**
- Web/app commands (development and production)
- Testing commands
- Utility commands

**Makefile.etl:**
- All ETL pipeline commands (extract, transform, load)
- Automatically included by main Makefile via `include Makefile.etl`

**Command Naming Convention:**
- **Development commands**: `make <command>` (e.g., `make extract-smk`, `make build`)
- **Production commands**: `make prod_<command>` (e.g., `make prod_extract-smk`, `make prod_start`)
- **[PROD] prefix**: Added to help text for all production commands

**Environment File Management:**
- **Local development**: Only `.env.dev` should exist (connects to local Docker PostgreSQL)
- **Production server**: Only `.env.prod` should exist (connects to cloud PostgreSQL)
- Both files are gitignored - never commit environment files

**Database Cleanup:**
- `make db-stop`: Stops and removes local PostgreSQL container (useful on server if accidentally started)

**Task Management:** See `AGENTS.md` for Beads workflow and task tracking.

### Essential Commands

**All development operations use the project Makefile** - run `make help` to see available commands.

```bash
make build          # Build development environment
make develop        # Start development server
make test           # Run all tests
make shell          # Open container shell

# ETL commands (local development)
make extract-smk    # Extract data from SMK museum
make transform      # Transform all museum data
make load-images    # Load images to S3

# Production ETL commands (on server)
make prod_extract-smk   # Extract data using production database
make prod_transform     # Transform using production database
make prod_load-images   # Load images using production database

# Database cleanup (on server)
make db-stop        # Stop/remove accidentally started local db container
```

## ETL Pipeline Architecture

**Status: ✅ Complete and production-ready**

The ETL pipeline consists of 4 sequential stages:

### 1. Extract (Museum APIs → Raw Metadata)
**Status: ✅ Done**

Fetches artwork metadata from museum APIs and stores in PostgreSQL `MetaDataRaw` table.

```bash
make extract-smk
make extract-cma
make extract-met
make extract-rma
```

**Key Components:**
- Museum-specific extractors in `etl/pipeline/extract/extractors/`
- Upsert using unique constraint (museum_slug + object_number)
- HTTP session reuse and retry logic
- **Duplicate prevention**: Both MET and RMA extractors detect and skip artworks with duplicate object_numbers (first occurrence wins)
  - Root cause: Public artwork identifiers are not guaranteed unique by design in either museum's data model
  - MET: ~0.3% duplicate accession numbers observed in practice
  - RMA: No duplicates observed yet, but safeguard prevents potential data corruption if they exist

### 2. Transform (Raw → Standardized Format)
**Status: ✅ Done**

Transforms museum-specific JSON to standardized `TransformedData` format.

```bash
make transform              # All museums
make transform-smk          # SMK only
make transform-cma          # CMA only
make transform-rma          # RMA only
make transform-met          # MET only
```

**Design Philosophy:**
- **Simple**: Transform everything every time - no complex state tracking
- **Museum-specific**: Optional filtering by museum slug
- **Type-safe**: Uses Pydantic models and dataclasses

**Key Components:**
- `TransformerArgs`: Dataclass for transformer inputs
- `TransformedArtworkData`: Pydantic model for validated output
- `transform_and_upsert()`: Single function using Django's `update_or_create()`
- Museum-specific transformers in `etl/pipeline/transform/transformers/`

**Benefits:**
- No hash-based staleness detection
- No complex state tracking
- Easy to understand and maintain
- Idempotent: safe to run multiple times

### 3. Load Images (S3 Bucket Upload)
**Status: ✅ Done**

Downloads thumbnail images from museum URLs and uploads to S3-compatible object storage.

```bash
make load-images-dev
make load-images-dev-small
```

**Architecture:** `etl/services/image_load_service.py`

**Design Philosophy:**
- **Simple boolean tracking**: Uses `image_loaded` field only
- **No hashing**: Removed complex hash-based change detection
- **Natural pagination**: Management command loop prevents infinite loops
- **Idempotent**: Processing same record twice doesn't re-upload

**Key Features:**
- Only processes records where `image_loaded=False`
- Rate limiting to be polite to museum APIs (0.2s/5s delays)
- Force reload via `reset_image_loaded_field()` (sets all flags to False)
- Batch processing with progress tracking

**Data Flow:**
1. Query `TransformedData` where `image_loaded=False`
2. Download image from `thumbnail_url` (museum API)
3. Resize image to max 800px (maintaining aspect ratio)
4. Upload to S3 bucket as `{museum}_{object_number}.jpg`
5. Set `image_loaded=True`

**Image Resizing:**
- All images resized before upload (max dimension: 800px)
- Aspect ratio always maintained (no distortion)
- RMA uses IIIF API to request 800px directly
- CMA/SMK/MET images resized client-side using Pillow
- Quality: JPEG at 85% quality
- Typical size: ~100-200KB (vs 1MB+ originals)
- Configurable via `IMAGE_MAX_DIMENSION` and `IMAGE_JPEG_QUALITY` env vars

**Image Delivery:**
- Currently using direct Linode Object Storage URLs (no CDN)
- Performance: ~200ms for US users, ~50ms for EU users with 100-200KB images
- Browser caching: 30 days (`max-age=2592000`)
- **Future CDN option**: If global performance becomes an issue, Cloudflare CDN can be added without code changes (just proxy DNS through Cloudflare). Decision deferred to focus on product features over infrastructure optimization.

### 4. Load Embeddings (CLIP → Qdrant)
**Status: ✅ Done**

Generates CLIP image embeddings and uploads to Qdrant vector database.

```bash
make load-embeddings-dev-small      # 10 records with delays
make load-embeddings-dev            # 100 records with delays
make load-embeddings-prod           # Production: 1000 records, slower
```

**Architecture:** `etl/services/embedding_load_service.py`

**Design Philosophy:**
- **Simple boolean tracking**: Uses vector-specific boolean fields
- **Active vector system**: Incremental activation of new embedding types
- **Prerequisite enforcement**: Only processes where `image_loaded=True`
- **No hashing**: Removed complex hash-based change detection
- **Idempotent**: Safe to run multiple times

**Active Vector Type System:**
```python
ACTIVE_VECTOR_TYPES = ["image_clip"]  # Easy to expand later

VECTOR_TYPE_TO_FIELD = {
    "image_clip": "image_vector_clip",    # Active - calculated
    "text_clip": "text_vector_clip",      # Inactive - zero vector
    "image_jina": "image_vector_jina",    # Inactive - zero vector
    "text_jina": "text_vector_jina",      # Inactive - zero vector
}
```

**Key Features:**
- Only processes records where `image_loaded=True` (prerequisite)
- Only calculates vectors in `ACTIVE_VECTOR_TYPES`
- Downloads images from **S3 bucket** (not museum APIs - faster!)
- CLIP image embedding generation (768 dimensions)
- Qdrant storage with 4 named vectors (active + placeholder zeros)
- Rate limiting for bucket (0.1s/2s delays)
- Force reload via `reset_vector_fields()` (resets active vector flags)

**Qdrant Collection Structure:**
- Collection: `artworks_etl_v1`
- 4 named vectors: `text_clip`, `image_clip`, `text_jina`, `image_jina`
- Metadata payload: museum, object_number, title, artist, production_date, work_types

**Data Flow:**
1. Query `TransformedData` where `image_loaded=True` AND at least one active vector is False
2. Download image from S3 bucket (fast!)
3. Generate CLIP embedding (768 dims)
4. Create Qdrant point with named vectors + payload
5. Upload to Qdrant
6. Set `image_vector_clip=True`

**Future Expansion:**
To activate text_clip vectors, simply add to `ACTIVE_VECTOR_TYPES`:
```python
ACTIVE_VECTOR_TYPES = ["image_clip", "text_clip"]
```

### ETL Pipeline Benefits

This 4-stage separation provides:
- **Isolation**: Image downloads separated from embedding generation
- **Retry flexibility**: Can retry images without recalculating embeddings
- **Parallelization**: Could run image/embedding loading in parallel
- **Clear failure recovery**: Missing images vs missing embeddings are separate concerns
- **Resource management**: Control GPU usage independently from network I/O

## Testing

### Framework
- **pytest with Django integration** (NOT Django's built-in test runner)
- **Test database**: Isolated `test_artsearch_dev` database (configured in settings.py)
- **No coverage reporting**: Removed for faster, cleaner test output

### Test Philosophy
- **What-focused**: Test business outcomes, not implementation details
- **Integration over unit**: Test entire pipeline flows rather than individual functions
- **End-to-end validation**: Test that data correctly flows through the system
- **Fewer, better tests**: High-value tests that catch real problems
- **Mock expensive dependencies**: S3, Qdrant, CLIP model - mock these for fast, reliable tests

### Test Suite
All ETL pipeline stages have integration tests:

1. **`test_extract_smk_integration.py`**
   - Fetches real SMK artwork from API
   - Stores in MetaDataRaw database
   - Tests idempotency (no duplicates)

2. **`test_extract_rma_integration.py`**
   - Fetches real RMA artwork from API
   - Stores in MetaDataRaw database
   - Tests idempotency (no duplicates)
   - Tests duplicate object_number detection (skips when same object_number exists with different museum_db_id)

3. **`test_extract_met_integration.py`**
   - Fetches real MET artwork from API
   - Stores in MetaDataRaw database
   - Tests idempotency (no duplicates)
   - Tests duplicate object_number detection (handles MET's ~0.3% duplicate accession numbers)

4. **`test_transform_smk_integration.py`**
   - Transforms MetaDataRaw → TransformedData
   - Verifies required fields extracted
   - Tests idempotency (update not create)

5. **`test_load_images_integration.py`**
   - Downloads images to S3 (mocked)
   - Updates `image_loaded` flag
   - Tests idempotency and reset functionality

6. **`test_load_embeddings_integration.py`**
   - Prerequisite check (`image_loaded=True` required)
   - Generates CLIP embeddings (mocked)
   - Uploads to Qdrant (mocked)
   - Validates Qdrant point structure
   - Tests active vector system
   - Tests idempotency and reset functionality

### Commands
```bash
make test              # Run all tests
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
```

### Test Strategy
- Use `@pytest.mark.unit` for fast unit tests (no external dependencies)
- Use `@pytest.mark.integration` for broader integration tests
- Use `@pytest.django_db` when database access is needed
- Use `@pytest.fixture` for clean test data setup
- Use `@patch` for mocking external dependencies (S3, Qdrant, CLIP, etc.)
- Use `@pytest.mark.parametrize` for efficient parameterized testing
- All tests must work with pytest, not `python manage.py test`

### Configuration
**pyproject.toml:**
- `--reuse-db`: Reuses test database for faster runs
- `--nomigrations`: Uses model introspection instead of running migrations
- `--tb=short`: Shorter tracebacks
- `-v`: Verbose output

**settings.py:**
```python
DATABASES = {
    "default": {
        ...
        "TEST": {
            "NAME": "test_artsearch_dev",  # Isolated test database
        },
    }
}
```

### Updating Test Database After Migrations

**Important**: The test suite uses `--nomigrations` which creates the test database from model introspection. When you add a new migration, you need to recreate the test database:

```bash
# Recreate test database with new model fields
pytest etl/tests --create-db

# Or for specific test file
pytest etl/tests/test_load_embeddings_integration.py --create-db
```

**Why this is needed:**
- `--reuse-db` flag reuses the existing test database for speed
- `--nomigrations` creates schema from models, not migrations
- After adding a field to a model, the reused test DB won't have that field
- `--create-db` drops and recreates the test database with current model structure

**When to use:**
- After creating new migrations (`python manage.py makemigrations`)
- When tests fail with "column does not exist" errors
- After pulling changes that include new migrations

## Search Features

### Query Types
1. **Text Search**: Natural language queries converted to CLIP embeddings
2. **Object Number Search**: Direct lookup by object number (e.g., "KMS1")
3. **Museum-Specific Search**: Format "museum:object_number" (e.g., "smk:KMS1")
4. **Similar Image Search**: Find visually similar artworks

### Filtering
- Filter by museum (SMK, CMA, RMA, MET)
- Filter by work type (painting, print, drawing, etc.)
- Results are paginated with 20 items per page

## Architectural Separation: ETL vs App

### Current Architecture

The repository contains two architecturally distinct components:

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

### Design Principle: Keep ETL and App Separate

**Why**: The ETL pipeline may be split into a separate repository in the future. Maintaining clear boundaries now makes this easier later.

**How**:
- **Avoid creating new cross-dependencies** between `etl/` and `artsearch/`
- **Accept intentional duplication** when it represents genuine architectural independence
  - Example: Museum API URLs defined in both extractors and museum clients serve different purposes
  - Extractors: Bulk data collection (search endpoints, pagination)
  - Museum clients: Individual object URL construction (single item lookups)

### Known Coupling Points

These are the current dependencies between ETL and artsearch app:

1. **`get_bucket_image_url()`** from `etl/services/bucket_service.py`
   - Used by: ETL image loader + artsearch frontend formatting
   - Reason: Both need to construct S3 URLs for thumbnails

2. **Museum client utilities** from `artsearch/src/services/museum_clients/utils.py`
   - Used by: ETL models (admin links) + artsearch frontend formatting
   - Reason: Both need to construct museum page/API URLs for individual objects

3. **`get_qdrant_service()`** from `artsearch/src/services/qdrant_service.py`
   - Used by: ETL embedding loader + ETL payload scripts + artsearch search service + artsearch stats service
   - Reason: Both need to interact with Qdrant vector database (ETL for writes, app for reads)

**Future split strategy**: When splitting repositories, these can be:
- Extracted to a shared package/library
- Duplicated in both repos (they're small and stable)
- Left as a dependency (one repo depends on the other)

**Current stance**: Don't solve this prematurely. The coupling is documented and minimal.

## Coding Conventions

- **Prefer simple, functional code** over complex OOP patterns
- **Only use classes when there's a clear benefit** - otherwise, use functions
- **Dataclasses/Pydantic models** for structured data, not full classes with methods
- **ABCs** can occasionally be useful (as in ETL transformers)
- **Type hints** especially for function signatures, plus type aliases for complex types
- **f-strings** instead of .format(), unless .format() is significantly clearer

## Important Instruction Reminders

- Prefer editing existing files rather than creating new ones.
- Only create new files when it's necessary for the requested change.
- Update CLAUDE.md when there are significant architectural or design changes.
- Don't commit, stage, or push any changes to the repository unless explicitly instructed to do so.
- **Refactor before testing**: If code is designed in a way that makes it difficult to test (e.g., global instances initialized at module level, tight coupling to external services), refactor it first to make it testable. Prefer simple patterns like:
  - Call functions directly instead of storing global instances
  - Use dependency injection or lazy initialization instead of module-level initialization
  - Keep functions pure and side-effect-free where possible
- **Testing**:
  - Run **ETL tests** (`make test-etl`) after changes to the ETL pipeline (extractors, transformers, image/embedding loaders, ETL models, or ETL services)
  - Run **app tests** (`make test-app`) after changes to artsearch views, view context builders, or search services
  - Run **all tests** (`make test`) after architectural changes that affect both components
  - For other changes (frontend templates, museum clients, utilities), tests are not required unless specifically requested
- Please review ETL tests after refactoring to ensure they still align with the updated code.
- Remember to run "make tailwind-start" when working on frontend templates to enable hot-reloading of Tailwind CSS.
