# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Semantic Art Search is a Django-based web application that uses Jina CLIP v2 to enable semantic search of artwork collections from multiple museums. Users search artworks using natural language and find visually or thematically similar pieces.

### Core Applications

- **artsearch**: Main Django app (search functionality, models, services, views)
- **etl**: Extract, Transform, Load pipeline for museum data
- **theme**: Tailwind CSS configuration
- **djangoconfig**: Django project configuration

### Data Flow

1. **ETL Pipeline**: Museum APIs → Raw metadata (PostgreSQL) → Transformed data → Images (S3) → Embeddings (Qdrant)
2. **Search Pipeline**: User query → Text embedding (Jina) → Qdrant vector search → Results
3. **Similar Image Search**: Object number → Retrieve image embedding → Vector similarity search

### Museum Integration

Six museums via their open APIs/data:
- **SMK**: Statens Museum for Kunst (Denmark)
- **CMA**: Cleveland Museum of Art
- **RMA**: Rijksmuseum Amsterdam
- **MET**: Metropolitan Museum of Art
- **AIC**: Art Institute of Chicago
- **NGA**: National Gallery of Art, Washington (bulk CSV open data on GitHub, no per-object API)

Each museum has a client in `artsearch/src/services/museum_clients/`

**Core Design Principle - Unique Public Identifiers:**
This project requires unique public artwork identifiers. They must be public-facing (accession numbers, not internal IDs), unique, and enforced. When museums don't provide unique identifiers (MET has ~0.3% duplicates, RMA potentially has some), the system uses "first occurrence wins" to maintain data integrity.

## Development Setup

### Environment

- **Config**: `artsearch/src/config.py` (Pydantic-based)
- **Env files**: `.env.dev` (local) or `.env.prod` (server) - never commit these
- **Dependencies**: Qdrant, PostgreSQL, Linode Object Storage (S3-compatible), Jina API

### Docker

- **Development**: `docker-compose.dev.yml` (includes local PostgreSQL)
- **Production**: `docker-compose.prod.yml` (cloud PostgreSQL, nginx proxy)

**Worktrees:** `docker-compose.dev.yml` sets the project name `semantic-art-search`, so all checkouts share one dev stack. To try a branch in a worktree, run `make develop` there: `web` is recreated to serve that checkout, keeping the same Postgres and Qdrant data; run it from the main checkout to switch back. New worktrees get `.env.dev` copied in via `.worktreeinclude` (Claude Code worktrees only; for others, copy it yourself). Run `make sync-db-local` from the main checkout, since `db` mounts `./db_dumps` from the checkout that started it.

### Commands

Run `make help` for all commands.

**Makefile structure:**
- `Makefile` - Web/app commands, testing, utilities
- `Makefile.etl` - All ETL pipeline commands (auto-included)

**Naming conventions:**
- `make <command>` - Development
- `make prod_<command>` - Production

See `.claude/rules/etl-pipeline.md` for ETL command patterns (`*-force`, `*-retry-failed`, etc.).

### Local Qdrant Data

Local search is only meaningful if the dev Qdrant collection holds real prod vectors. `make qdrant-check-vectors` reports zero-norm vectors per museum. To refresh dev from prod (prod Qdrant has no published port, so this goes via a snapshot file):

1. On the server: `make prod_qdrant-snapshot-export` (saves to `qdrant_snapshots/`)
2. Locally: `scp` the file into `qdrant_snapshots/` (the export prints the command)
3. Locally: `make sync-qdrant-local` (replaces the dev collection, then runs the vector check)

See `QDRANT_MANAGEMENT.md` for details.

### Local PostgreSQL Data

The same flow mirrors the prod ETL/app tables into the dev DB (`make db-counts` shows rows per museum):

1. On the server: `make prod_db-export` (data-only `pg_dump` into `db_dumps/`; `make prod_export-all` also takes a Qdrant snapshot so both match)
2. Locally: `scp` the file into `db_dumps/` (the export prints the command)
3. Locally: `make sync-db-local` (checks dev has the same migrations as the dump, then replaces the tables in one transaction, so a failed restore leaves dev unchanged)

Synced tables: `etl_metadataraw`, `etl_transformeddata`, `artsearch_artworkstats`, `artsearch_artworkdescription`, `artsearch_artmapdata`, `artsearch_examplequery` (`DB_SYNC_TABLES` in `Makefile`). Search/image logs, users, sessions and Django framework tables are never copied. Dev Postgres must have the same major version as prod (17); `pg_dump` runs in a `postgres:17` container (`PG_CLIENT_IMAGE`), and the dev `db` container mounts `db_dumps/` read-only.

Dev moved from Postgres 16 to 17 to match prod, and 17 won't start on a volume created by 16. To move an older dev DB, run `docker compose -f docker-compose.dev.yml exec -T db pg_dumpall -U devuser > backup.sql` while it is still on 16, then `docker compose -f docker-compose.dev.yml down`, `docker volume rm semantic-art-search_postgres_data`, start the db on 17 and pipe `backup.sql` into `psql -U devuser -d postgres` (the "already exists" errors for the role and database are expected).

### Deployment

Deploy from merged `master`: on the server, in the repo, run `make prod_deploy` (aborts if the server checkout has local changes, then `git pull --ff-only` + `make prod_start`, then `docker image prune -f` to drop the previous, now untagged web image). Only the `web` container is rebuilt and recreated; Qdrant, nginx and the cloud database are untouched.

- `entrypoint.prod.sh` runs migrations, builds Tailwind CSS and collects static files on every start, so no manual migrate or CSS step is needed on the server. With `DEBUG` off, static files use `ManifestStaticFilesStorage`: URLs carry a content hash (`styles.<hash>.css`) so browsers never keep stale CSS after a deploy, and `{% static %}` raises if `collectstatic` hasn't run or a referenced file is missing. (The committed `theme/static/css/dist/styles.css` is only used locally; run `make tailwind-start` while editing templates or new classes won't show up in dev.)
- Expect 502s for ~20s after a deploy while that startup runs.
- Verify: the home page returns 200 and contains a marker from the change; for search changes, hit the HTMX endpoint `/artworks/?query=...` (not `/get-artworks/`).

## Search Features

### Query Types

1. **Text Search**: Natural language → embeddings
2. **Object Number Search**: Direct lookup (e.g., "KMS1")
3. **Museum-Specific Search**: Format "museum:object_number" (e.g., "smk:KMS1")
4. **Similar Image Search**: Find visually similar artworks
5. **Image Upload Search**: Upload, drop or paste your own image (camera button in the search input) to find artworks that look like it

### Filtering

- Filter by museum (SMK, CMA, RMA, MET, AIC, NGA)
- Filter by work type (painting, print, drawing, etc.)
- Filter by production year (`year_from` / `year_to`): keeps artworks whose production period overlaps the range; artworks with no dates are excluded once a bound is set. Implemented twice with the same rules: `filter_by_year_range()` (PostgreSQL `ArtworkStats`, used for browse mode and counts) and `_year_range_conditions()` (Qdrant search). Years come from the `production_date_start`/`end` payload fields, copied into `ArtworkStats` by `load_artwork_stats`
- Paginated (20 items per page)

### Search Mode Selection

The search form has two submit buttons, "Visual Search" (`image`) and "Title Search" (`title`); the clicked button sets the hidden `model` input, and the highlighted one shows the mode of the current results so users can re-run the same query in the other mode with one click. Enter in the search input re-runs the currently highlighted mode. Example queries always run as Visual Search (they describe how artworks look).

New searches (offset 0) return an `HX-Replace-Url` header (`make_home_url()` in `context_builders.py`) so the browser URL holds query, filters and mode; loading that URL restores the search. Filters covering everything are omitted from the URL.

- **Visual** (`image`, default): Searches `image_jina` vectors — finds visually similar artworks
- **By title** (`title`): Searches `text_jina` vectors — finds artworks by title/description match

All modes use Jina CLIP v2 (256d) for text embedding. Similarity search always uses `image_jina`.

**Key Files:**
- `artsearch/src/constants/search_modes.py`: Mode definitions and vector name mapping
- `artsearch/src/services/jina_embedder.py`: Jina embedder (API)
- `artsearch/src/services/qdrant_service.py`: Vector search

**Qdrant vectors per artwork:** `image_jina` (256d), `text_jina` (256d), `image_clip` (768d, populated for all museums except NGA (zeros); currently unused by search — see #88), `text_clip` (768d, zeros — unused)

### Image Upload Search

`artsearch/src/services/image_upload_service.py`. The browser downscales the image (1024px, `downscaleImage()` in `home.html`) and POSTs it to `/artworks/image/` (rate limited 10/min, 100/hour). The server validates it with Pillow, downscales to 512px (one Jina tile, so one 4,000-token charge), embeds it with Jina and caches the vector for an hour in its own Django cache, `uploaded_images` (per-process LocMem, fine with prod's single gunicorn worker), keyed by a hash of the image bytes. It returns that key; the form puts it in the hidden `image` input and submits, so `/artworks/?image=<key>` searches `image_jina` with the usual filters and pagination. Uploads are never stored. Image searches aren't shareable: the key is left out of `HX-Replace-Url`, and after it expires (or a restart/deploy) the user is asked to upload again. Typing a text query, clicking an example query or clicking Title Search clears the image.

**Cost control and usage:** every upload is logged in `ImageSearchLog` (timestamp, status `embedded`/`cached`/`daily_cap`/`rejected`/`failed`, source `web`/`api`; the image itself is not stored). Jina calls are capped site-wide at `DAILY_EMBEDDING_CAP` (1000) per UTC day, counted from that table (`embedded` + `failed`, since failed calls may still be billed), so the cap survives restarts and many-IP abuse can't drain the prepaid Jina balance that text search also needs. The row is written before the Jina call and counted after, so concurrent uploads can't overshoot. Cached re-uploads and invalid files don't count. Over the cap, uploads get HTTP 429. Usage per day: `make image-search-stats` / `make prod_image-search-stats`, or the Django admin.

## Artwork Pages

Every artwork has a shareable page at `/artwork/<museum_slug>/<object_number>/` (`artwork_page_view`, template `artwork.html`), linked from the artwork title on search result cards and in the popup (the image still opens the popup). A **Share** button in the popup and on the page uses `shareLink()` (`base.html`): the system share menu on touch devices, otherwise copy to clipboard. It shows the image, metadata, 12 visually similar artworks (stored `image_jina` vector, no Jina call; "Show more" appends the next 12 in place via the HTMX endpoint `/artwork/<museum_slug>/<object_number>/similar/?offset=N`) and per-artwork `<title>`, canonical URL and Open Graph/Twitter tags. Pages override the `title` and `meta` blocks in `base.html`.

- **High-resolution images and deep zoom (IIIF)**: for SMK, NGA and RMA, `artsearch/src/utils/iiif.py` derives the museum's IIIF image service from the full-resolution `image_url` in `TransformedData` (one lookup per page view; the URL formats are pinned by tests against the transformers). The page shows our bucket thumbnail, swaps in a 1600px IIIF image once it has loaded, and offers a Zoom button that lazy-loads OpenSeadragon (cdnjs) on the same image. The search popup gets the same larger image (it asks `/artworks/large-image/`, DB-only, on open) but no zoom yet. CMA and MET have no IIIF; AIC's IIIF server is behind a Cloudflare bot challenge, so it's left out.
- **Object numbers can contain `/`, spaces, brackets, commas** (e.g. SMK `KKS10208/5`, MET `Burdick 218, N220.35`), so artwork routes use `<path:object_number>`, with the `similar/` routes listed before the detail/page routes (page and REST API).
- **AI descriptions**: the page and the search popup only show an already cached description (the popup fetches it on open from `/artworks/description/cached/`, which is DB-only and not rate limited); new ones are generated on click. Never generate on page load, or crawlers would trigger OpenAI calls for every page.
- **Sitemap**: `/sitemap.xml` (index) and `/sitemap-<section>.xml?p=N`, built from `ArtworkStats`, 10k URLs per page, cached for a day. Paths are built by `artwork_page_path()` (`artsearch/sitemaps.py`) rather than `reverse()`, which was too slow at this volume; a test keeps the two identical.
- **robots.txt** points to the sitemap and disallows `/artworks/` (HTMX search), `/api/` and `/htmx/` so crawlers don't spend Jina API calls.

## Art Map

`/map/` (`map.html`, deck.gl) plots every artwork at precomputed UMAP coordinates of its `image_jina` vector, made offline by `make art-map` (`generate_art_map`) and stored in `ArtMapData` (binary geometry plus metadata JSON, served at `/map/data/...`). Clicking a dot opens a panel linking to the artwork page and to Find similar (`/?query=<slug>:<object_number>`). "Show on map" on artwork pages and in the search popup links to `/map/?artwork=<slug>/<object_number>` (`make_map_url()`), which flies to the artwork and rings it, or says it isn't on the map yet (artworks loaded after the last `make art-map`). Points are coloured by work type, museum or century (by `production_date_start`, falling back to the end year; groups and slugs are `CENTURY_SLUGS` in `constants/museums.py`, the last one being "undated"). Clicking a legend item hides or shows that museum, work type or century; all three kinds of filter apply in every colour mode. "Show all" and "Hide all" act on the current colour mode only (Hide all, then click one item to isolate it). They run on the GPU via deck.gl's `DataFilterExtension` (category filter), so hidden points are neither drawn nor picked. The chevron next to the colour-mode buttons collapses the legend items; it starts collapsed below 640px wide (phones), and while collapsed still says how many museums/work types/centuries are hidden. The map keeps the selection, view (`x`, `y`, `z`), colour mode (`color=museum`, `color=century`) and filters (`hide_museums=smk,rma`, `hide_types=print`, `hide_centuries=1500s,undated`) in the URL, so map links can be shared. The geometry blob is `count, x, y, museum, work type, century`; the page reads blobs made before the century array was added and hides the Century mode until `make art-map` is re-run.

## REST API

JSON API at `/api/`. Code in `artsearch/api/views.py` and `artsearch/api/urls.py`.

| Endpoint | Description |
|----------|-------------|
| `GET /api/museums/` | List museums (`slug`, `full_name`) |
| `GET /api/work-types/` | List searchable work types |
| `GET /api/search/?query=...` | Semantic search across artworks |
| `POST /api/search/image/` | Artworks resembling an uploaded image (multipart field `image`, max 10 MB; filters/paging in the query string). Rate-limited 10/min, 100/hour |
| `GET /api/random/` | Random artworks (optional `seed` for reproducibility) |
| `GET /api/artworks/<museum_slug>/<object_number>/` | Single artwork detail |
| `GET /api/artworks/<museum_slug>/<object_number>/similar/` | Visually similar artworks |

**Common query parameters** (search, random, similar): `offset`, `limit` (max 24), `museums` (repeatable), `work_types` (repeatable), `model` (`image`/`title`, default `image`), `year_from` / `year_to` (production year range).

Search, similar, and random endpoints are **rate-limited** (30/min, 200/hour per IP).

New searches (first page only) from the website and the API (`/api/search/`, `/api/search/image/`) are logged in `SearchLog` with mode, narrowing filters, year range and `source` (`web`/`api`). Image searches use mode `upload` and an empty query; `ImageSearchLog` separately records each upload and its Jina cost. Similar and random requests aren't logged.

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
- **Review before reporting done**: after non-trivial code changes (logic in views, services, ETL, models/migrations, anything touching cost or rate limits), run the `code-review` skill on the diff once tests pass. Fix confirmed findings, re-run the relevant tests, and in the final summary list any findings deliberately skipped and why. Skip the review for docs, copy, styling-only template changes and trivial edits.
- Run `make tailwind-start` when working on frontend templates
- To rebuild the compiled CSS once (e.g. after adding new Tailwind classes), run `make tailwind-build`, never a bare `manage.py tailwind build` in the container: its npm cache is unwritable there, and the build deletes `theme/static/css/dist/styles.css` before failing
