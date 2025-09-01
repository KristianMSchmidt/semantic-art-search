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

### Key Services (`artsearch/src/services/`)
- **search_service.py**: Main search orchestration and query analysis
- **qdrant_service.py**: Vector database operations and search functionality
- **clip_embedder.py**: CLIP model management and embedding generation
- **museum_clients/**: API clients for different museums (SMK, CMA, RMA, MET)
- **bucket_service.py**: AWS S3 integration for image storage

### Configuration
- **artsearch/src/config.py**: Environment-based configuration using Pydantic
- Requires `.env.dev` or `.env.prod` files for environment variables
- Key dependencies: Qdrant, PostgreSQL, AWS S3, CLIP model

## Development Commands

### Docker Development Environment
```bash
# Build development environment
make build

# Start development server (with hot reload)
make develop

# Stop development server
make stop

# Open shell in running container
make shell

# Open Django shell
make djangoshell
```

### Database Operations
```bash
# Generate migrations
make migrations

# Apply migrations
make migrate
```

### Tailwind CSS
```bash
# Install Tailwind dependencies
make tailwind-install

# Start Tailwind watcher (run during development)
make tailwind-start
```

### Data ETL Operations

#### Current ETL Implementation Status
- **Extract (E)**: ✅ Complete - Museum API clients extract raw data
- **Transform (T)**: ✅ Complete - Transformer scripts in `etl/pipeline/transform/transformers/`
  - `cma_transformer.py` - Cleveland Museum of Art data transformation
  - `met_transformer.py` - Metropolitan Museum of Art data transformation  
  - `rma_transformer.py` - Rijksmuseum Amsterdam data transformation
  - `smk_transformer.py` - Statens Museum for Kunst data transformation
- **Load (L)**: 🚧 Next phase - Multi-step loading process:
  1. Download and store artwork images in AWS S3 bucket
  2. Generate CLIP embeddings for images and text metadata
  3. Load processed data and embeddings into Qdrant vector database

```bash
# Extract data from individual museums (production)
make extract-smk
make extract-cma
make extract-rma
make extract-met

# Load phase commands (in development)
make upload-to-qdrant-SMK
make upload-to-qdrant-CMA
make upload-to-qdrant-RMA
make upload-to-qdrant-MET
```

### Code Quality
```bash
# Format and lint Python code
ruff format .
ruff check .
```

### Testing

The project uses pytest with Django integration for comprehensive testing:

```bash
# Run all tests
make test

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-extract       # ETL extraction tests only

# Generate coverage reports
make test-coverage      # Creates HTML coverage report in htmlcov/
```

#### Test Configuration
- **Framework**: pytest with pytest-django, pytest-mock, pytest-cov
- **Configuration**: `pyproject.toml` contains pytest settings
- **Test Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
- **Coverage**: Tracks coverage for both `etl` and `artsearch` apps
- **Database**: Uses `--reuse-db` and `--nomigrations` for faster test runs

#### Current Test Coverage
- **Overall Project**: ~24% coverage
- **ETL Extractors**: 22-47% coverage with integration tests for all museum APIs
- **Test Structure**:
  - `etl/tests/test_extract.py` - Comprehensive extraction pipeline tests
  - Unit tests for core utilities and data storage functions  
  - Integration tests with mocked HTTP responses for museum APIs (SMK, CMA, RMA, MET)
  - Orchestration tests for the main extraction workflow

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
