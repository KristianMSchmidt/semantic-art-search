# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Semantic Art Search is a Django-based web application that uses CLIP (Contrastive Language-Image Pre-training) to enable semantic search of artwork collections from multiple museums. The system allows users to search artworks using natural language queries and find visually or thematically similar pieces.

## Key Architecture Components

### Core Applications
- **artsearch**: Main Django app containing search functionality, models, services, and views
- **etl**: Extract, Transform, Load app for processing museum data (complete ETL pipeline in `@etl/`)
- **theme**: Tailwind CSS theme configuration
- **djangoconfig**: Django project configuration

### Data Flow Architecture
1. **ETL Pipeline**: Museum APIs → Raw metadata (PostgreSQL) → Processed embeddings (Qdrant)
2. **Search Pipeline**: User query → CLIP text embedding → Qdrant vector search → Results
3. **Similar Image Search**: Object number → Retrieve image embedding → Vector similarity search

### Key Services
- **Search**: CLIP-based semantic search and query analysis (`artsearch/src/services/`)
- **Museums**: API clients for SMK, CMA, RMA, MET (`museum_clients/`)
- **Storage**: Vector database (Qdrant) and image storage (S3)

### Configuration
- **artsearch/src/config.py**: Environment-based configuration using Pydantic
- Requires `.env.dev` or `.env.prod` files for environment variables
- Key dependencies: Qdrant, PostgreSQL, AWS S3, CLIP model

## Development Commands

**All development operations use the project Makefile** - run `make help` to see available commands.

### Essential Commands
```bash
make build      # Build development environment
make develop    # Start development server
make test       # Run all tests
make shell      # Open container shell
```

### ETL Pipeline Commands
```bash
# Extract (museum APIs → raw data)
make extract-smk
make extract-cma
make extract-met
make extract-rma

# Transform (raw → standardized format)
make transform              # All museums
make transform-smk          # SMK only
make transform-cma          # CMA only
make transform-rma          # RMA only
make transform-met          # MET only

# Load Images (thumbnails → S3)
make load-images-dev
make load-images-dev-small

# Load Embeddings (CLIP → Qdrant)
make load-embeddings-dry-run        # Test run, no changes
make load-embeddings-dev-small      # 10 records with delays
make load-embeddings-dev            # 100 records with delays
make load-embeddings-prod           # Production: 1000 records, slower
```

### ETL Pipeline Status
- **Extract**: ✅ Museum API clients for all 4 museums
- **Transform**: ✅ Simplified data transformation (all museums complete)
- **Load 1**: ✅ Image storage (S3)
- **Load 2**: ✅ CLIP embedding generation + Qdrant vector DB

### Testing
- **Framework**: pytest with Django integration (NOT Django's built-in test runner)
- **Key commands**: `make test`, `make test-unit`, `make test-integration`
- **Test Strategy**:
  - Use `@pytest.mark.unit` for fast unit tests (no external dependencies)
  - Use `@pytest.mark.integration` for broader integration tests
  - Use `@pytest.django_db` when database access is needed
  - Use `@pytest.fixture` for clean test data setup
  - Use `@patch` for mocking external dependencies (API calls, etc.)
  - Use `@pytest.mark.parametrize` for efficient parameterized testing
  - All tests must work with pytest, not `python manage.py test`

## Museum Integration

The system integrates with four major museums through their open APIs:
- **SMK**: Statens Museum for Kunst (Denmark)
- **CMA**: Cleveland Museum of Art
- **RMA**: Rijksmuseum Amsterdam
- **MET**: Metropolitan Museum of Art

Each museum has a dedicated client in `artsearch/src/services/museum_clients/` that handles API-specific data extraction and formatting.

## Search Features

### Query Types
1. **Text Search**: Natural language queries converted to CLIP embeddings
2. **Object Number Search**: Direct lookup by inventory number (e.g., "KMS1")
3. **Museum-Specific Search**: Format "museum:object_number" (e.g., "smk:KMS1")
4. **Similar Image Search**: Find visually similar artworks

### Filtering
- Filter by museum (SMK, CMA, RMA, MET)
- Filter by work type (painting, print, drawing, etc.)
- Results are paginated with 20 items per page

## Environment Setup

Required environment variables (in `.env.dev` or `.env.prod`):
- Database: `POSTGRES_*` variables
- Vector DB: `QDRANT_URL`, `QDRANT_API_KEY`
- Storage: `AWS_*` variables for S3
- Django: `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG`

## Production Deployment

The system uses Docker Compose with separate configurations for development and production:
- **Development**: `docker-compose.dev.yml` - single container with hot reload
- **Production**: `docker-compose.prod.yml` - includes nginx reverse proxy

Production commands use `make production_*` prefix (e.g., `make production_start`, `make production_stop`).

## ETL Pipeline Architecture

### Transform Service (Simplified Design)
The transform pipeline (`etl/pipeline/transform/`) has been radically simplified for maintainability:

**Design Philosophy:**
- **Simple**: Transform everything every time - no complex state tracking
- **Museum-specific**: Optional filtering by museum slug
- **Clean separation**: Transform stage only handles data transformation, not processing state
- **Type-safe**: Uses dataclasses and proper typing throughout

**Key Components:**
- `TransformerArgs`: Dataclass containing all transformer inputs (museum_slug, object_number, museum_db_id, raw_json)
- `TransformerFn`: Type alias for transformer functions
- `transform_and_upsert()`: Single function to transform and upsert records using Django's `update_or_create()`
- Museum-specific transformers in `etl/pipeline/transform/transformers/`

**Data Flow:**
1. Query `MetaDataRaw` records (optionally filtered by museum)
2. For each record: Create `TransformerArgs` → Call transformer → Upsert to `TransformedData`
3. Uses `update_or_create()` based on unique constraint (museum_slug + object_number)

**Benefits:**
- No hash-based staleness detection complexity
- No state tracking (removed `is_transformed` field)
- Perfect for occasional bulk operations
- Easy to understand and maintain
- Type-safe function interfaces

**Current Status:**
- ✅ All transformers (SMK, CMA, RMA, MET) fully migrated to new interface
- ✅ Transform pipeline testing complete with successful results:
  - SMK: 180 records transformed
  - CMA: 223 records transformed
  - RMA: 134 records transformed (105 filtered for rights/images)
  - MET: 318 records transformed (638 filtered for work types)

### Load Embeddings Service
The embedding generation pipeline (`etl/pipeline/load/load_embeddings/service.py`) provides:

**Features:**
- CLIP image embedding generation (768 dimensions)
- Qdrant vector storage with 4 named vectors (future-proofed):
  - `image_clip`: CLIP image embeddings (active)
  - `text_clip`, `text_jina`, `image_jina`: Zero vectors (placeholders)
- Smart change detection (thumbnail URL hashing)
- Rate limiting to protect museum APIs
- Resume capability with `image_vector_clip` boolean tracking

**Key Methods:**
- `get_records_needing_processing()`: Query unprocessed/stale records
- `should_process_embedding()`: Intelligent processing decisions
- `process_single_record()`: Generate embedding + upload to Qdrant
- `run_batch_processing()`: Batch processing with progress tracking

**Collection:** Uses `artworks_etl_v1` collection in Qdrant with metadata fields:
- `museum`, `object_number`, `title`, `artist`, `production_date`
- `work_types`, `searchable_work_types`

**Rate Limiting:** Default delays protect museum APIs:
- Development: 0.2s between records, 5s between batches
- Production: 0.5s between records, 10s between batches


## Coding conversions:
 - Always use f-strings instead of .format(), unless the .format() version is significantly clearer.
 - Only uses classes when there is a clear benefit. Otherwise, use functions.
 - Mostly I only want dataclasses or Pydantic models for structured data, not full classes with methods. But ABCs can occasionaaly be useful, as in the ETL transformers.
 - I like type hints, especially for function signatures. But also type aliases for complex types.
 - I prefer simple, functional code over complex OOP patterns.
