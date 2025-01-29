## ----------------------------------------------------------------------
## Makefile for portfolio.kristianms.com
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

# -------------- CLI ------------- #
find-similar:
	python -m artsearch.src.cli.find_similar_images

text-search:
	python -m artsearch.src.cli.text_search

upload-to-qdrant:
	python -m artsearch.src.cli.upload_to_qdrant
