## ----------------------------------------------------------------------
## Makefile for semantic-art-search.kristianms.com
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
	docker-compose -f docker-compose.dev.yml build

develop:  ## Run development server
	docker-compose -f docker-compose.dev.yml up --remove-orphans

stop: ## Stop development server
	docker-compose -f docker-compose.dev.yml down --remove-orphans

shell:  ## Open shell in running docker development container
	docker-compose -f docker-compose.dev.yml exec web /bin/bash

djangoshell:  ## Open django shell in running docker development container
	docker-compose -f docker-compose.dev.yml exec web python manage.py shell


# ---------- Data ---------- #
adhoc: # Adhoc scripts only used during development
	docker-compose -f docker-compose.dev.yml exec web python -m artsearch.src.scripts.adhoc

upload-to-qdrant: ## upload images to qdrant
	docker-compose -f docker-compose.dev.yml exec web python -m artsearch.src.scripts.upload_to_qdrant

stats: ## Print out collection stats
	docker-compose -f docker-compose.dev.yml exec web python -m artsearch.src.scripts.collection_stats

projection: ## Run projection
	docker-compose -f docker-compose.dev.yml exec web python -m artsearch.src.scripts.datascience_experiments.2d_proj_artists


# ---------- Production ---------- #
production_stop: ## Stop production server
	docker-compose -f docker-compose.prod.yml down --remove-orphans

production_start: ## Start production server as daemon
	docker-compose -f docker-compose.prod.yml up --build --remove-orphans -d

production_djangologs: ## Show django logs
	docker logs semantic-art-searchkristianmscom_web_1

production_accesslogs: ## Show nginx access logs
	docker logs semantic-art-searchkristianmscom_nginx_1

production_terminal: # Open shell in running docker production container
	docker-compose -f docker-compose.prod.yml exec web /bin/bash

production_shell:  ## Open shell in running docker development container
	docker-compose -f docker-compose.prod.yml exec web /bin/bash

production_djangoshell:  ## Open django shell in running docker development container
	docker-compose -f docker-compose.prod.yml exec web python manage.py shell
