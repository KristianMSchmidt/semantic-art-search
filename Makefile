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

shell:  ## Open shell in running docker development container
	docker compose -f docker-compose.dev.yml exec web /bin/bash

djangoshell:  ## Open django shell in running docker development container
	docker compose -f docker-compose.dev.yml exec web python manage.py shell

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


# ---------- Production ---------- #
production_stop: ## Stop production server
	docker compose -f docker-compose.prod.yml down --remove-orphans

production_start: ## Start production server as daemon
	docker compose -f docker-compose.prod.yml up --build --remove-orphans -d

production_djangologs: ## Show django logs
	docker logs semantic-art-searchkristianmscom-web-1

production_accesslogs: ## Show nginx access logs
	docker logs semantic-art-searchkristianmscom-nginx-1

production_shell: # Open shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web /bin/bash

production_djangoshell:  ## Open django shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web python manage.py shell
