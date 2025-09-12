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

### ETL Pipeline Status
- **Extract**: ✅ Museum API clients for all 4 museums
- **Transform**: ✅ Data transformation to standardized format
- **Load 1**: ✅ Image storage (S3)
- **Load 2**:  embedding generation (CLIP) + vector DB (Qdrant)

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
