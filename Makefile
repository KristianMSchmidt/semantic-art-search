## ----------------------------------------------------------------------
## Makefile for semantic-art-search.kristianms.com
##
## Used for both development and production. See targets below.
## ----------------------------------------------------------------------

help:   # Show this help.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)


# ---------- Development ---------- #

tailwind-start:  ## start tailwind (should be running while developing)
	python manage.py tailwind start

tailwind-build: ## build minified production tailwind css
	python manage.py tailwind build

dj:  ## run django server
	python manage.py runserver

adhoc: # Adhoc srcripts only used during development
	python -m artsearch.src.cli.adhoc

# -------------- CLI ------------- #
find-similar: ## find similar images
	python -m artsearch.src.cli.find_similar_images

text-search: # search by text
	python -m artsearch.src.cli.text_search

# ---------- Data Operations ---------- #
upload-to-qdrant: # upload images to qdrant
	python -m artsearch.src.cli.upload_to_qdrant

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
