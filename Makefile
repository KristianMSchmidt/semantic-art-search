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

dj: # Run django server (almost) as in production
	python manage.py runserver

run-gunicorn: # Run gunicorn server (to mimic production)
	gunicorn djangoconfig.wsgi -b 0.0.0.0:8017 --workers=1 --timeout=300 --log-level=debug --reload

adhoc: # Adhoc scripts only used during development
	python -m artsearch.src.scripts.adhoc


# ---------- Data Operations ---------- #
upload-to-qdrant: ## upload images to qdrant
	python -m artsearch.src.scripts.upload_to_qdrant


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

production_shell:  ## Open django shell in running docker development container
	docker-compose -f docker-compose.prod.yml exec web python manage.py shell
