# Semantic Art Search

[Semantic Art Search](https://semantic-art-search.com) lets you search open museum collections by describing what you're looking for, or by uploading an image. It covers seven museums and also plots every artwork on a map of visual similarity.

To use the site, or to read how it works in plain language and which museums it covers, see the [About page](https://semantic-art-search.com/about/). The rest of this README is for developers.

## How it works

Jina CLIP v2 embeds images and text into a shared 256-dimensional vector space, and Qdrant ranks artworks by vector similarity to the query:

- **Visual Search** (the default) compares the query with image vectors, so it can find a cat in a painting whose record never mentions one.
- **Title Search** compares the query with vectors of the titles.
- **Similar artworks** and **image upload search** use the same image vectors.
- **The art map** is a precomputed UMAP projection of the image vectors, drawn with deck.gl.

Filters for museum, work type and production year run on stored metadata.

## Stack

- Django 5.1 with HTMX, Alpine.js and Tailwind CSS
- PostgreSQL for raw and transformed museum data, statistics and logs
- Qdrant for vector search
- S3-compatible object storage for thumbnails
- Jina API for embeddings, OpenAI API for the artwork descriptions generated on request

## Project layout

| Directory | Contents |
|-----------|----------|
| `artsearch/` | The web app: search, artwork pages, art map and REST API |
| `etl/` | The pipeline: museum APIs → raw metadata → transformed data → thumbnails → embeddings |
| `theme/` | Tailwind configuration and compiled CSS |
| `djangoconfig/` | Django project settings |

## Running it locally

You need Docker, plus accounts for the Jina and OpenAI APIs and an S3-compatible bucket.

1. Create `.env.dev` in the repository root with the settings listed in `artsearch/src/config.py`.
2. Build and start the stack, which includes PostgreSQL and Qdrant:

   ```bash
   make build
   make develop
   ```

3. In another terminal, apply the migrations:

   ```bash
   make migrate
   ```

The site runs at http://localhost:8000, but it has no artworks until you run the pipeline. Run `make help` to see all commands.

## Loading data

Each museum has its own targets for each pipeline step, for example for SMK:

```bash
make extract-smk
make transform-smk
make load-images-smk
make load-embeddings-smk
```

Then build the tables and data that the site reads:

```bash
make load-artwork-stats    # statistics for browsing and filter counts
make compute-colorfulness  # scores for the default home page view
make art-map               # coordinates for the art map
```

## Tests

```bash
make test      # everything
make test-app  # the web app
make test-etl  # the pipeline
```

The tests run with pytest inside the dev container, so the stack needs to be running.

## REST API

A JSON API is available at `/api/`. No key is needed, and search, similar and random requests are rate limited to 30 a minute and 200 an hour per IP.

| Endpoint | Description |
|----------|-------------|
| `GET /api/museums/` | List museums |
| `GET /api/work-types/` | List searchable work types |
| `GET /api/search/?query=...` | Search artworks |
| `POST /api/search/image/` | Find artworks resembling an uploaded image (multipart field `image`, max 10 MB; limited to 10 a minute and 100 an hour) |
| `GET /api/random/` | Random artworks (optional `seed`) |
| `GET /api/artworks/<museum_slug>/<object_number>/` | One artwork |
| `GET /api/artworks/<museum_slug>/<object_number>/similar/` | Visually similar artworks |

Search, random and similar accept `offset`, `limit` (max 24), `museums` and `work_types` (both repeatable), `year_from` and `year_to`. Search also accepts `model` (`image` or `title`, default `image`).

## Data and licence

The code is under the [MIT License](LICENSE). The artworks and their data come from the museums' open data programmes, and only works they have released as public domain or open access are included. The [About page](https://semantic-art-search.com/about/) lists and links to each museum.

## Get in touch

Questions, ideas or corrections are welcome: open an [issue](https://github.com/KristianMSchmidt/semantic-art-search/issues) or message me on [LinkedIn](https://www.linkedin.com/in/kristian-m%C3%B8ller-schmidt-516b9170/).
