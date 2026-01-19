---
paths:
  - "etl/**"
  - "Makefile.etl"
---

# ETL Pipeline

**Status: Complete and production-ready**

4 sequential stages: Extract → Transform → Load Images → Load Embeddings

## Commands

All ETL commands are in `Makefile.etl`. Run `make help` to see available commands.

**Naming conventions:**
- `make <command>` - Development (uses `.env.dev`)
- `make prod_<command>` - Production (uses `.env.prod`)
- `*-force` variants - Force reload (ignores existing data)
- `*-retry-failed` variants - Retry only failed records
- `*-all` variants - Process all museums at once

**Examples:**
```bash
make extract-smk           # Extract SMK (dev)
make prod_extract-smk      # Extract SMK (prod)
make load-images-met-force # Force reload MET images
make load-embeddings-retry-failed  # Retry failed embeddings
```

## Stage 1: Extract (Museum APIs → Raw Metadata)

Fetches artwork metadata from museum APIs into PostgreSQL `MetaDataRaw` table.

**Key Components:**
- Extractors in `etl/pipeline/extract/extractors/`
- Upsert using unique constraint (museum_slug + object_number)
- HTTP session reuse and retry logic
- **Duplicate prevention**: MET and RMA extractors skip duplicate object_numbers (first occurrence wins)

**MET API Data Model:**
- `objectID`: Internal database ID (used in MET's URLs)
- `accessionNumber`: Public catalog number, NOT unique (~0.3% duplicates)
- System uses `accessionNumber` as `object_number` for UX, accepts ~0.3% data loss

**RMA API Data Model:**
- Uses OAI-PMH XML/RDF structure
- `object_number` extracted from `dc:identifier` (not guaranteed unique)
- No duplicates observed yet, but safeguard exists

## Stage 2: Transform (Raw → Standardized)

Transforms museum-specific JSON to standardized `TransformedData` format.

**Design:** Simple - transform everything every time, no state tracking. Idempotent.

**Key Components:**
- `TransformerArgs`: Dataclass for inputs
- `TransformedArtworkData`: Pydantic model for output
- `transform_and_upsert()`: Uses Django's `update_or_create()`
- Transformers in `etl/pipeline/transform/transformers/`

## Stage 3: Load Images (S3 Upload)

Downloads thumbnails and uploads to S3-compatible storage.

**Architecture:** `etl/services/image_load_service.py`

**Data Flow:**
1. Query `TransformedData` where `image_loaded=False`
2. Download from `thumbnail_url`
3. Resize to max 800px (aspect ratio maintained)
4. Upload to S3 as `{museum}_{object_number}.jpg`
5. Set `image_loaded=True`

**Key Details:**
- Rate limiting configured per-museum in Makefile.etl
- Image quality: JPEG 85%, ~100-200KB
- Configurable: `IMAGE_MAX_DIMENSION`, `IMAGE_JPEG_QUALITY` env vars

## Stage 4: Load Embeddings (CLIP → Qdrant)

Generates embeddings and uploads to Qdrant vector database.

**Architecture:** `etl/services/embedding_load_service.py`

**Active Vector System:**
```python
ACTIVE_VECTOR_TYPES = ["image_clip", "image_jina"]

VECTOR_TYPE_TO_FIELD = {
    "image_clip": "image_vector_clip",
    "text_clip": "text_vector_clip",
    "image_jina": "image_vector_jina",
    "text_jina": "text_vector_jina",
}
```

**Data Flow:**
1. Query where `image_loaded=True` AND active vector is False
2. Download image from S3 bucket
3. Generate embedding (CLIP: 768 dims, Jina: 1024 dims)
4. Upload to Qdrant with named vectors + payload
5. Set vector field to True

**Qdrant Collection:** `artworks_etl_v1`
- 4 named vectors: `text_clip`, `image_clip`, `text_jina`, `image_jina`
- Payload: museum, object_number, title, artist, production_date, work_types

## Pipeline Benefits

- **Isolation**: Image downloads separate from embedding generation
- **Retry flexibility**: Retry images without recalculating embeddings
- **Clear failure recovery**: Missing images vs missing embeddings are separate
- **Resource management**: Control GPU usage independently from network I/O
