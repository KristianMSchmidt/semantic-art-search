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

test-unit:  ## Run unit tests only
	docker compose -f docker-compose.dev.yml exec web pytest -m unit

test-integration:  ## Run integration tests only (with migrations)
	docker compose -f docker-compose.dev.yml exec web pytest -m integration




# ---------- Production ---------- #
production_stop: ## Stop production server
	docker compose -f docker-compose.prod.yml down --remove-orphans

production_start: ## Start production server as daemon
	docker compose -f docker-compose.prod.yml up --build --remove-orphans -d

production_djangologs: ## Show django logs
	docker logs live-app-web-1

production_accesslogs: ## Show nginx access logs
	docker logs live-app-nginx-1

production_shell: ## Open shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web /bin/bash

production_djangoshell:  ## Open django shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web python manage.py shell


# ---------- Data ---------- #

adhoc: # Adhoc scripts only used during development
	python -m artsearch.src.scripts.adhoc

stats: ## Get work type stats
	python -m artsearch.src.services.museum_stats_service

update-payload: ## Update collection payload
	python -m artsearch.src.scripts.update_payload


# ---------- ETL ---------- #
# Note: ETL commands use 'docker compose run --rm' to create one-time containers
# that spin up, execute the command, and clean up automatically (no permanent container needed)

extract-smk: ## Extract raw data from SMK
	docker compose -f docker-compose.dev.yml run --rm web python manage.py extract -m smk

extract-cma: ## Extract raw data from CMA
	docker compose -f docker-compose.dev.yml run --rm web python manage.py extract -m cma

extract-rma: ## Extract raw data from RMA
	docker compose -f docker-compose.dev.yml run --rm web python manage.py extract -m rma

extract-met: ## Extract raw data from MET
	docker compose -f docker-compose.dev.yml run --rm web python manage.py extract -m met

extract-all: ## Extract raw data from ALL museums
	docker compose -f docker-compose.dev.yml run --rm web python manage.py extract --all

extract-met-force: ## Force refetch raw data from MET (ignores existing data)
	docker compose -f docker-compose.dev.yml run --rm web python manage.py extract -m met --force-refetch

transform:  ## Transform all records for all museums
	docker compose -f docker-compose.dev.yml run --rm web python manage.py transform --batch-size 100

transform-smk:  ## Transform all records for SMK museum only
	docker compose -f docker-compose.dev.yml run --rm web python manage.py transform --museum smk --batch-size 100

transform-cma:  ## Transform all records for CMA museum only
	docker compose -f docker-compose.dev.yml run --rm web python manage.py transform --museum cma --batch-size 100

transform-rma:  ## Transform all records for RMA museum only
	docker compose -f docker-compose.dev.yml run --rm web python manage.py transform --museum rma --batch-size 100

transform-met:  ## Transform all records for MET museum only
	docker compose -f docker-compose.dev.yml run --rm web python manage.py transform --museum met --batch-size 100


# ETL Load Images
load-images-smk:  ## Load thumbnail images for SMK museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum smk --batch-size 50 --delay 0.2 --batch-delay 5

load-images-cma:  ## Load thumbnail images for CMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum cma --batch-size 50 --delay 0.1 --batch-delay 2

load-images-rma:  ## Load thumbnail images for RMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum rma --batch-size 50 --delay 0.1 --batch-delay 2

load-images-met:  ## Load thumbnail images for MET museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum met --batch-size 50 --delay 0.2 --batch-delay 5

load-images-all:  ## Load thumbnail images for all museums
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --batch-size 100 --delay 0.2 --batch-delay 5

# ETL Load Images - Force Reload
load-images-smk-force:  ## Force reload all thumbnail images for SMK museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum smk --force --batch-size 50 --delay 0.2 --batch-delay 5

load-images-cma-force:  ## Force reload all thumbnail images for CMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum cma --force --batch-size 50 --delay 0.1 --batch-delay 2

load-images-rma-force:  ## Force reload all thumbnail images for RMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum rma --force --batch-size 50 --delay 0.1 --batch-delay 2

load-images-met-force:  ## Force reload all thumbnail images for MET museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --museum met --force --batch-size 50 --delay 0.2 --batch-delay 5

load-images-all-force:  ## Force reload all thumbnail images for all museums
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --force --batch-size 100 --delay 0.2 --batch-delay 5

# ETL Load Images - Retry Failed
load-images-retry-failed:  ## Retry previously failed images for specified museum (use --museum flag)
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_images --retry-failed --batch-size 50 --delay 0.2 --batch-delay 5

# ETL Load Embeddings
load-embeddings-smk:  ## Generate CLIP embeddings for SMK museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum smk --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-cma:  ## Generate CLIP embeddings for CMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum cma --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-rma:  ## Generate CLIP embeddings for RMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum rma --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-met:  ## Generate CLIP embeddings for MET museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum met --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-all:  ## Generate CLIP embeddings for all museums
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --batch-size 100 --delay 0.1 --batch-delay 2

# ETL Load Embeddings - Force Reload
load-embeddings-smk-force:  ## Force regenerate embeddings for SMK museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum smk --force --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-cma-force:  ## Force regenerate embeddings for CMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum cma --force --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-rma-force:  ## Force regenerate embeddings for RMA museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum rma --force --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-met-force:  ## Force regenerate embeddings for MET museum
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --museum met --force --batch-size 50 --delay 0.1 --batch-delay 2

load-embeddings-all-force:  ## Force regenerate embeddings for all museums
	docker compose -f docker-compose.dev.yml run --rm web python manage.py load_embeddings --force --batch-size 100 --delay 0.1 --batch-delay 2
