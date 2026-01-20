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

## Design Principle: Accept Coupling Where It Reflects Shared Dependencies

These two components are **genuinely interdependent by design**:
- ETL produces data that the app consumes
- They share config, a vector DB, and S3 buckets
- The coupling reflects real architectural relationships

**Guidance**:
- Don't duplicate code to create artificial separation
- Accept bidirectional dependencies where they're logical
- Document coupling points so the architecture is clear

## Known Coupling Points

### ETL → ArtsSearch (10 files)

| Category | ETL Files | Imports from ArtsSearch |
|----------|-----------|------------------------|
| **Config** | `bucket_service.py`, `embedding_load_service.py`, `copy_bucket.py`, `load_artwork_stats.py`, `migrate_qdrant_cloud.py` | `artsearch.src.config` |
| **Services** | `embedding_load_service.py`, `update_payload.py` | `QdrantService`, `get_clip_embedder`, `get_jina_embedder` |
| **Constants** | `pipeline/transform/utils.py` | `SEARCHABLE_WORK_TYPES`, `get_standardized_work_type` |
| **Museum Utils** | `models.py`, `extract.py`, `factory.py` | `get_museum_slugs`, `get_museum_page_url`, `get_museum_api_url` |
| **Models** | `load_artwork_stats.py` | `ArtworkStats` |

### ArtsSearch → ETL (3 files)

| ArtsSearch File | Import from ETL |
|-----------------|-----------------|
| `qdrant_formatting.py` | `get_bucket_image_url` |
| `artwork_description/service.py` | `get_bucket_image_url` |
| `artwork_description/metadata_processors/rma.py` | `RmaTransformer` |

## Why This Coupling Is Acceptable

1. **No deployment independence needed** - Both components deploy together
2. **The coupling is logical** - ETL needs embedders to create embeddings; app needs bucket URLs to show images
3. **Duplication creates maintenance burden** - Two copies of shared code means two places to update
4. **A shared package adds complexity** - Would be a third thing to maintain with unclear payoff
