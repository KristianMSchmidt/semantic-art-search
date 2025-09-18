## ----------------------------------------------------------------------
## Makefile for semantic-art-search.com
##
## Used for both development and production. See targets below.
## ----------------------------------------------------------------------


help:   # Show this help.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)


# ---------- Development ---------- #
tailwind-install:  ## install tailwind
	python manage.py tailwind install

tailwind-start:  ## start tailwind (should be running while developing)
	python manage.py tailwind start

build:  ## Build or rebuild development docker image
	docker compose -f docker-compose.dev.yml build

develop:  ## Run development server
	docker compose -f docker-compose.dev.yml up --remove-orphans

stop: ## Stop development server
	docker compose -f docker-compose.dev.yml down --remove-orphans

migrations:  ## Run migrations
	docker compose -f docker-compose.dev.yml exec web python manage.py makemigrations

migrate:  ## Apply migrations
	docker compose -f docker-compose.dev.yml exec web python manage.py migrate

shell:  ## Open shell in running docker development container
	docker compose -f docker-compose.dev.yml exec web /bin/bash

djangoshell:  ## Open django shell in running docker development container
	docker compose -f docker-compose.dev.yml exec web python manage.py shell

test:  ## Run all tests with pytest
	docker compose -f docker-compose.dev.yml exec web pytest

test-extract:  ## Run extraction pipeline tests only
	docker compose -f docker-compose.dev.yml exec web pytest etl/tests/test_extract.py

test-transform:  ## Run transformation pipeline tests only
	docker compose -f docker-compose.dev.yml exec web pytest etl/tests/test_transform.py

test-load-images:  ## Run image loading pipeline tests only
	docker compose -f docker-compose.dev.yml exec web pytest etl/tests/test_load_images_unit.py

test-load-embeddings-unit:  ## Run embedding loading unit tests only
	docker compose -f docker-compose.dev.yml exec web pytest etl/tests/test_load_embeddings_unit.py

test-load-embeddings:  ## Run embedding loading integration tests only
	docker compose -f docker-compose.dev.yml exec web pytest etl/tests/test_load_embeddings.py

test-unit:  ## Run unit tests only
	docker compose -f docker-compose.dev.yml exec web pytest -m unit

test-integration:  ## Run integration tests only (with migrations)
	docker compose -f docker-compose.dev.yml exec web pytest -m integration --migrations

test-coverage:  ## Run tests with coverage report
	docker compose -f docker-compose.dev.yml exec web pytest --cov-report=html



# ---------- Data ---------- #

adhoc: # Adhoc scripts only used during development
	python -m artsearch.src.scripts.adhoc

upload-to-qdrant-SMK: ## upload SMK data to qdrant
	python -m artsearch.src.scripts.upload_to_qdrant.SMK

upload-to-qdrant-CMA: ## upload CMA data images to qdrant
	python -m artsearch.src.scripts.upload_to_qdrant.CMA

upload-to-qdrant-RMA: ## upload RMA data images to qdrant
	python -m artsearch.src.scripts.upload_to_qdrant.RMA

upload-to-qdrant-MET: ## upload Met data images to qdrant
	python -m artsearch.src.scripts.upload_to_qdrant.MET

stats: ## Get work type stats
	python -m artsearch.src.services.museum_stats_service

update-payload: ## Update collection payload
	python -m artsearch.src.scripts.update_payload


# ---------- ETL ---------- #
extract-smk: ## upsert-raw-data from SMK
	docker compose -f docker-compose.prod.yml exec web python manage.py extract -m smk

extract-cma: ## upsert-raw-data from CMA
	docker compose -f docker-compose.prod.yml exec web python manage.py extract -m cma

extract-rma: ## upsert-raw-data from RMA
	docker compose -f docker-compose.prod.yml exec web python manage.py extract -m rma

extract-met: ## upsert-raw-data from MET
	docker compose -f docker-compose.prod.yml exec web python manage.py extract -m met

extract-all: ## upsert-raw-data from ALL museums
	docker compose -f docker-compose.prod.yml exec web python manage.py extract --all

transform:  ## Run ETL transform pipeline with default settings (batch_size=1000, start_id=0)
	docker compose -f docker-compose.prod.yml exec web python manage.py transform --batch-size 1000 --start-id 0

# ETL Load Images
load-images-dry-run:  ## Preview image loading without actual downloads (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_images --dry-run --batch-size 10

load-images-smk:  ## Load thumbnail images for SMK museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_images --museum smk --batch-size 50 --delay 0.3 --batch-delay 10

load-images-cma:  ## Load thumbnail images for CMA museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_images --museum cma --batch-size 50 --delay 0.3 --batch-delay 10

load-images-rma:  ## Load thumbnail images for RMA museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_images --museum rma --batch-size 50 --delay 0.3 --batch-delay 10

load-images-met:  ## Load thumbnail images for MET museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_images --museum met --batch-size 50 --delay 0.3 --batch-delay 10

load-images-all:  ## Load thumbnail images for all museums (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_images --batch-size 100 --delay 0.2 --batch-delay 5

# Production ETL Load Images
production_load-images-dry-run:  ## Preview image loading without actual downloads (production)
	docker compose -f docker-compose.prod.yml exec web python manage.py load_images --dry-run --batch-size 10

production_load-images-all:  ## Load thumbnail images for all museums (production)
	docker compose -f docker-compose.prod.yml exec web python manage.py load_images --batch-size 200 --delay 0.1 --batch-delay 3

# ETL Load Embeddings (Development)
load-embeddings-dry-run:  ## Preview embedding generation without actual processing (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --dry-run --batch-size 10

load-embeddings-smk:  ## Generate CLIP embeddings for SMK museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --museum smk --batch-size 50 --delay 0.3 --batch-delay 10

load-embeddings-cma:  ## Generate CLIP embeddings for CMA museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --museum cma --batch-size 50 --delay 0.3 --batch-delay 10

load-embeddings-rma:  ## Generate CLIP embeddings for RMA museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --museum rma --batch-size 50 --delay 0.3 --batch-delay 10

load-embeddings-met:  ## Generate CLIP embeddings for MET museum (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --museum met --batch-size 50 --delay 0.3 --batch-delay 10

load-embeddings-all:  ## Generate CLIP embeddings for all museums (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --batch-size 100 --delay 0.2 --batch-delay 5

load-embeddings-force:  ## Force regenerate embeddings for all records (development)
	docker compose -f docker-compose.dev.yml exec web python manage.py load_embeddings --force --batch-size 50 --delay 0.3 --max-batches 3

# Production ETL Load Embeddings
production_load-embeddings-dry-run:  ## Preview embedding generation without actual processing (production)
	docker compose -f docker-compose.prod.yml exec web python manage.py load_embeddings --dry-run --batch-size 10

production_load-embeddings-all:  ## Generate CLIP embeddings for all museums (production)
	docker compose -f docker-compose.prod.yml exec web python manage.py load_embeddings --batch-size 200 --delay 0.1 --batch-delay 3

production_load-embeddings-force:  ## Force regenerate embeddings for all records (production)
	docker compose -f docker-compose.prod.yml exec web python manage.py load_embeddings --force --batch-size 100 --delay 0.2 --batch-delay 5


# ---------- Production ---------- #
production_stop: ## Stop production server
	docker compose -f docker-compose.prod.yml down --remove-orphans

production_start: ## Start production server as daemon
	docker compose -f docker-compose.prod.yml up --build --remove-orphans -d

production_djangologs: ## Show django logs
	docker logs semantic-art-searchkristianmscom-web-1

production_accesslogs: ## Show nginx access logs
	docker logs semantic-art-searchkristianmscom-nginx-1

production_shell: ## Open shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web /bin/bash

production_djangoshell:  ## Open django shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web python manage.py shell
