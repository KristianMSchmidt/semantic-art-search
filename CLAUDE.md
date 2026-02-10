# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Semantic Art Search is a Django-based web application that uses CLIP to enable semantic search of artwork collections from multiple museums. Users search artworks using natural language and find visually or thematically similar pieces.

### Core Applications

- **artsearch**: Main Django app (search functionality, models, services, views)
- **etl**: Extract, Transform, Load pipeline for museum data
- **theme**: Tailwind CSS configuration
- **djangoconfig**: Django project configuration

### Data Flow

1. **ETL Pipeline**: Museum APIs → Raw metadata (PostgreSQL) → Transformed data → Images (S3) → Embeddings (Qdrant)
2. **Search Pipeline**: User query → Text embedding (CLIP or Jina) → Qdrant vector search → Results
3. **Similar Image Search**: Object number → Retrieve image embedding → Vector similarity search

### Museum Integration

Five museums via their open APIs:
- **SMK**: Statens Museum for Kunst (Denmark)
- **CMA**: Cleveland Museum of Art
- **RMA**: Rijksmuseum Amsterdam
- **MET**: Metropolitan Museum of Art
- **AIC**: Art Institute of Chicago

Each museum has a client in `artsearch/src/services/museum_clients/`

**Core Design Principle - Unique Public Identifiers:**
This project requires unique public artwork identifiers. They must be public-facing (accession numbers, not internal IDs), unique, and enforced. When museums don't provide unique identifiers (MET has ~0.3% duplicates, RMA potentially has some), the system uses "first occurrence wins" to maintain data integrity.

## Development Setup

### Environment

- **Config**: `artsearch/src/config.py` (Pydantic-based)
- **Env files**: `.env.dev` (local) or `.env.prod` (server) - never commit these
- **Dependencies**: Qdrant, PostgreSQL, Linode Object Storage (S3-compatible), CLIP model

### Docker

- **Development**: `docker-compose.dev.yml` (includes local PostgreSQL)
- **Production**: `docker-compose.prod.yml` (cloud PostgreSQL, nginx proxy)

### Commands

Run `make help` for all commands.

**Makefile structure:**
- `Makefile` - Web/app commands, testing, utilities
- `Makefile.etl` - All ETL pipeline commands (auto-included)

**Naming conventions:**
- `make <command>` - Development
- `make prod_<command>` - Production

See `.claude/rules/etl-pipeline.md` for ETL command patterns (`*-force`, `*-retry-failed`, etc.).

## Search Features

### Query Types

1. **Text Search**: Natural language → embeddings
2. **Object Number Search**: Direct lookup (e.g., "KMS1")
3. **Museum-Specific Search**: Format "museum:object_number" (e.g., "smk:KMS1")
4. **Similar Image Search**: Find visually similar artworks

### Filtering

- Filter by museum (SMK, CMA, RMA, MET, AIC)
- Filter by work type (painting, print, drawing, etc.)
- Paginated (20 items per page)

### Embedding Model Selection

Users select via radio button UI:
- **Auto**: Smart selection based on query type
- **CLIP**: OpenAI CLIP (ViT-L/14) - 768d, local model
- **Jina**: Jina CLIP v2 - 256d, API-based

**Smart Auto Selection:**
- Similarity search → Jina
- Art historical queries (movements, styles) → CLIP
- General text → Jina

**Key Files:**
- `artsearch/src/constants/embedding_models.py`: Model definitions, resolution logic
- `artsearch/src/services/clip_embedder.py`: CLIP embedder (singleton)
- `artsearch/src/services/jina_embedder.py`: Jina embedder (API)
- `artsearch/src/services/qdrant_service.py`: Vector search with model selection

## Coding Conventions

- **Prefer simple, functional code** over complex OOP patterns
- **Only use classes when there's a clear benefit** - otherwise, use functions
- **Dataclasses/Pydantic models** for structured data, not full classes with methods
- **Type hints** especially for function signatures
- **f-strings** instead of .format()

## Instructions

- Prefer editing existing files rather than creating new ones
- Update CLAUDE.md when there are significant architectural or design changes
- Don't commit, stage, or push unless explicitly instructed
- **Refactor before testing**: If code is hard to test (global instances, tight coupling), refactor first
- **Testing** (see `.claude/rules/testing.md` for details):
  - `make test-etl` after ETL changes
  - `make test-app` after artsearch view/service changes
  - `make test` after architectural changes
  - **After creating a migration**, the test DB must be recreated: run tests with `--create-db` flag (e.g., `docker compose -f docker-compose.dev.yml exec web pytest artsearch/tests --create-db`). The `pytest-django` test DB is cached and won't pick up new migrations automatically.
- Run `make tailwind-start` when working on frontend templates
