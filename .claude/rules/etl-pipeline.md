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

**NGA Data Model:**
- No per-object API: the full collection is published as CSV files on GitHub (https://github.com/NationalGalleryOfArt/opendata), updated daily
- Extractor downloads `objects.csv` + `published_images.csv` and joins them; each run upserts everything
- `accessionnum` (unique in practice) is `object_number`; `objectid` is `museum_db_id` (used in page URLs)
- Only paintings for now (`ALLOWED_CLASSIFICATIONS` in the extractor; the transformer also supports drawings and prints)
- Only objects with an open access (`openaccess=1`) primary image are included; images via NGA's IIIF API
- For undated works NGA fills `beginyear`/`endyear` with the artist's lifespan, so the transformer stores no production dates when `displaydate` is empty, "n.d." or "date unknown"

**FNG (Finnish National Gallery) Data Model:**
- No open per-object API (its search API needs a key): the whole collection is one gzipped JSON dump at `https://kokoelma.kansallisgalleria.fi/api/v1/objects` (~29 MB gzipped, ~275 MB of JSON, ~89k objects, CC0). The extractor streams it (`iter_json_array`), since `json.load` would take ~1.4 GB of memory; each run upserts everything
- `inventoryNumber` (e.g. `A I 445`, `A II 841:297`; unique among included works) is `object_number`; `objectId` is `museum_db_id` (used in page URLs)
- Only standalone artworks (`category.en == "artwork"`, not sketchbook pages, letters or archive items) classified as painting, miniature or Japanese woodblock print (`ALLOWED_CLASSIFICATIONS`), with a CC0 image. Only works by artists who died over 70 years ago have images. Prints and drawings are left out on purpose (colour charts in many print photos, faint pencil studies), and sculpture until there is a searchable sculpture work type
- Titles: English if present, else Finnish or Swedish. Dates equal to the artist's lifespan are a placeholder for undated works, so they are stored as unknown
- Images are served up to 4000px (thumbnail from the 1000px version); no IIIF

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

## Stage 4: Load Embeddings (Jina → Qdrant)

Generates embeddings and uploads to Qdrant vector database.

**Architecture:** `etl/services/embedding_load_service.py`

**Active Vector System:**
```python
ACTIVE_VECTOR_TYPES = ["image_jina", "text_jina"]  # CLIP vectors get zeros

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
3. Generate embedding via the Jina API (256 dims)
4. Upload to Qdrant with named vectors + payload
5. Set vector field to True

### Jina Image Preprocessing (Cost vs Quality Decision)

**Background:** Jina CLIP v2 charges by tokens. Images larger than 512×512 are tiled into 512×512 chunks, each costing 4,000 tokens. A 1000×1000 image costs 4× more than a pre-resized 512×512 image.

**Decision (Jan 2025):** We currently pass full S3 URLs directly to Jina without local preprocessing. This means:
- Higher API costs (images are tiled server-side)
- Higher quality embeddings (more detail captured)
- All 180k artworks were embedded this way for consistency

**If re-embedding in the future:** Consider adding local resize-to-512×512 preprocessing in `jina_embedder.py` before API calls. But you MUST re-embed ALL images to maintain consistency — mixing tiled and pre-resized embeddings will degrade search quality.

**Qdrant Collection:** `artworks_etl_v1`
- 4 named vectors: `text_clip`, `image_clip`, `text_jina`, `image_jina`
- Payload: museum, object_number, title, artist, production_date, work_types

## After Loading: Artwork Stats and Colourfulness

`make load-artwork-stats` copies Qdrant payloads into `ArtworkStats` (counts, filters, browse) and sets `excluded_from_default_view` from raw MET credit lines (tobacco trade cards). It then reloads the web server (`make reload-web` / `make prod_reload-web`, a gunicorn HUP on prod, so no downtime), since the museum and work type counts are cached in-process (`museum_stats_service.py`) and a new museum would otherwise show no results until the next restart. Then `make compute-colorfulness` downloads each new artwork's bucket thumbnail and stores a colourfulness score, used to pick colourful artworks for the default home page view. It only scores rows without a score (~80/s, so the full collection takes ~40 min); `*-force` rescores all. It also reloads the web server afterwards, since the default view's artwork count is cached in-process too (`count_default_view_artworks` in `browse_service.py`).

## Pipeline Benefits

- **Isolation**: Image downloads separate from embedding generation
- **Retry flexibility**: Retry images without recalculating embeddings
- **Clear failure recovery**: Missing images vs missing embeddings are separate
- **Resource management**: Control GPU usage independently from network I/O
