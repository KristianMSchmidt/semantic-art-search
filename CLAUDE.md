# CLAUDE.private.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**PRIVATE FILE**: This is gitignored and won't be committed to the repository.

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
- **Development**: `docker-compose.dev.yml` - single container with hot reload
- **Production**: `docker-compose.prod.yml` - includes nginx reverse proxy
- Production commands use `make production_*` prefix

### Essential Commands

**All development operations use the project Makefile** - run `make help` to see available commands.

```bash
make build      # Build development environment
make develop    # Start development server
make test       # Run all tests
make shell      # Open container shell
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

## Coding Conventions

- **Prefer simple, functional code** over complex OOP patterns
- **Only use classes when there's a clear benefit** - otherwise, use functions
- **Dataclasses/Pydantic models** for structured data, not full classes with methods
- **ABCs** can occasionally be useful (as in ETL transformers)
- **Type hints** especially for function signatures, plus type aliases for complex types
- **f-strings** instead of .format(), unless .format() is significantly clearer

## Important Instruction Reminders

- Prefer editing existing files rather than creating new ones.
- Only create new files when it’s necessary for the requested change.
- Update claude.private.md when there are significant architectural or design changes.
- Don't commit, stage, or push any changes to the repository unless explicitly instructed to do so.
- Please run ETL tests after making changes to ensure everything works as expected.
- Please review ETL tests after changes refactoring to ensure they still align with the updated code.
