## ----------------------------------------------------------------------
## Makefile for semantic-art-search.com
##
## Used for both development and production. See targets below.
## ----------------------------------------------------------------------

.DEFAULT_GOAL := help

include Makefile.etl

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

test-etl:  ## Run ETL tests only
	docker compose -f docker-compose.dev.yml exec web pytest etl/tests

test-app:  ## Run artsearch app tests only
	docker compose -f docker-compose.dev.yml exec web pytest artsearch/tests




# ---------- Production ---------- #
prod_stop: ## [PROD] Stop production server
	docker compose -f docker-compose.prod.yml down --remove-orphans

prod_start: ## [PROD] Start production server as daemon
	docker compose -f docker-compose.prod.yml up --build --remove-orphans -d

prod_djangologs: ## [PROD] Show django logs
	docker logs live-app-web-1

prod_accesslogs: ## [PROD] Show nginx access logs
	docker logs live-app-nginx-1

prod_shell: ## [PROD] Open shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web /bin/bash

prod_djangoshell:  ## [PROD] Open django shell in running docker production container
	docker compose -f docker-compose.prod.yml exec web python manage.py shell


# ---------- Data / Reporting ---------- #

stats: ## Get work type stats
	python -m artsearch.src.services.museum_stats_service


# ---------- Database Utilities ---------- #

db-stop: ## Stop and remove local db container (cleanup for server)
	docker compose -f docker-compose.dev.yml stop db
	docker compose -f docker-compose.dev.yml rm -f db
