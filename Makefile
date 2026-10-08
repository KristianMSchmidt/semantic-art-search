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

test-openai:  ## Test OpenAI API key with database artwork (default: KMS1 smk)
	#docker compose -f docker-compose.dev.yml exec web python test_openai.py KMS8791 smk
	docker compose -f docker-compose.dev.yml exec web python test_openai.py KMSsp340 smk

test-openai-fast:  ## Test fast label generation (metadata-only, gpt-4o-mini)
	docker compose -f docker-compose.dev.yml exec web python test_openai_fast.py

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


# ---------- Art Map ---------- #

art-map: ## Generate UMAP 2D map data (saves to PostgreSQL)
	docker compose -f docker-compose.dev.yml run --rm web sh -c "pip install umap-learn==0.5.11 && python manage.py generate_art_map"

prod_art-map: ## [PROD] Generate UMAP 2D map data on production (saves to PostgreSQL)
	docker compose -f docker-compose.prod.yml run --rm --no-deps web sh -c "pip install umap-learn==0.5.11 && python manage.py generate_art_map"


# ---------- Data / Reporting ---------- #

stats: ## Get work type stats
	python -m artsearch.src.services.museum_stats_service


# ---------- Qdrant Vector Database ---------- #

qdrant-info: ## Show collection info (point count, vectors, indices)
	docker compose -f docker-compose.dev.yml exec web curl -s http://qdrant:6333/collections/artworks_prod_v1 | python3 -m json.tool

qdrant-health: ## Check Qdrant health status
	docker compose -f docker-compose.dev.yml exec web curl -s http://qdrant:6333/health

qdrant-collections: ## List all collections
	docker compose -f docker-compose.dev.yml exec web curl -s http://qdrant:6333/collections | python3 -m json.tool

qdrant-logs: ## Show Qdrant container logs
	docker compose -f docker-compose.dev.yml logs qdrant --tail=50

qdrant-ui: ## Instructions for accessing Qdrant Web UI
	@echo "Qdrant Web UI is running at http://localhost:6333/dashboard"
	@echo "Access it by opening http://localhost:6333/dashboard in your browser"

qdrant-snapshot: ## Create a snapshot of the collection
	docker compose -f docker-compose.dev.yml exec web curl -X POST http://qdrant:6333/collections/artworks_prod_v1/snapshots

qdrant-stats: ## Show collection statistics (quick summary)
	@echo "Collection: artworks_prod_v1"
	@docker compose -f docker-compose.dev.yml exec web curl -s http://qdrant:6333/collections/artworks_prod_v1 | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Points: {data['result']['points_count']:,}\"); print(f\"Status: {data['result']['status']}\"); print(f\"Vectors: {', '.join(data['result']['config']['params']['vectors'].keys())}\")"

prod_qdrant-info: ## [PROD] Show production collection info
	docker compose -f docker-compose.prod.yml exec web curl -s http://qdrant:6333/collections/artworks_prod_v1 | python3 -m json.tool

prod_qdrant-health: ## [PROD] Check production Qdrant health
	docker compose -f docker-compose.prod.yml exec web curl -s http://qdrant:6333/health

prod_qdrant-collections: ## [PROD] List all production collections
	docker compose -f docker-compose.prod.yml exec web curl -s http://qdrant:6333/collections | python3 -m json.tool

prod_qdrant-logs: ## [PROD] Show production Qdrant logs
	docker compose -f docker-compose.prod.yml logs qdrant --tail=50

prod_qdrant-ui-tunnel: ## [PROD] Print SSH tunnel command for Qdrant Web UI (run on server)
	@QDRANT_IP=$$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' $$(docker compose -f docker-compose.prod.yml ps -q qdrant) | awk '{print $$1}'); \
	echo "==================================================================="; \
	echo "Qdrant has no published port, so tunnel to the container IP."; \
	echo ""; \
	echo "1. Open SSH tunnel from your LOCAL machine:"; \
	echo "   ssh -L 6335:$$QDRANT_IP:6333 your-server-address"; \
	echo ""; \
	echo "2. Open in browser: http://localhost:6335/dashboard"; \
	echo ""; \
	echo "(Local port 6335 avoids clashing with the dev Qdrant on 6333."; \
	echo " The container IP can change when the container is recreated.)"; \
	echo "==================================================================="

prod_qdrant-snapshot: ## [PROD] Create a snapshot of the production collection
	docker compose -f docker-compose.prod.yml exec web curl -X POST http://qdrant:6333/collections/artworks_prod_v1/snapshots

prod_qdrant-stats: ## [PROD] Show production collection statistics
	@echo "Collection: artworks_prod_v1 (Production)"
	@docker compose -f docker-compose.prod.yml exec web curl -s http://qdrant:6333/collections/artworks_prod_v1 | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Points: {data['result']['points_count']:,}\"); print(f\"Status: {data['result']['status']}\"); print(f\"Vectors: {', '.join(data['result']['config']['params']['vectors'].keys())}\")"

# ---------- Syncing prod Qdrant to dev ---------- #
# 1. On server:  make prod_qdrant-snapshot-export
# 2. Locally:    scp server:<repo>/qdrant_snapshots/<name>.snapshot qdrant_snapshots/
# 3. Locally:    make sync-qdrant-local

prod_qdrant-snapshot-export: ## [PROD] Create a snapshot and save it to qdrant_snapshots/ (for copying to dev)
	@mkdir -p qdrant_snapshots
	@echo "Creating snapshot of artworks_prod_v1 (this can take a few minutes)..."
	@NAME=$$(docker compose -f docker-compose.prod.yml exec -T web curl -sf -X POST http://qdrant:6333/collections/artworks_prod_v1/snapshots | sed -n 's/.*"name":"\([^"]*\)".*/\1/p'); \
	test -n "$$NAME" || { echo "Snapshot creation failed"; exit 1; }; \
	echo "Downloading $$NAME..."; \
	docker compose -f docker-compose.prod.yml exec -T web curl -sf http://qdrant:6333/collections/artworks_prod_v1/snapshots/$$NAME > qdrant_snapshots/$$NAME \
		|| { echo "Download failed"; rm -f qdrant_snapshots/$$NAME; exit 1; }; \
	docker compose -f docker-compose.prod.yml exec -T web curl -sf -o /dev/null -X DELETE http://qdrant:6333/collections/artworks_prod_v1/snapshots/$$NAME; \
	echo "Saved $$(pwd)/qdrant_snapshots/$$NAME ($$(du -h qdrant_snapshots/$$NAME | cut -f1))"; \
	echo "Copy it to your machine with:"; \
	echo "  scp your-server-address:$$(pwd)/qdrant_snapshots/$$NAME qdrant_snapshots/"

sync-qdrant-local: ## Replace dev Qdrant collection with a prod snapshot (SNAPSHOT=path, default: newest in qdrant_snapshots/)
	@SNAPSHOT="$(SNAPSHOT)"; SNAPSHOT=$${SNAPSHOT:-$$(ls -t qdrant_snapshots/*.snapshot 2>/dev/null | head -1)}; \
	test -f "$$SNAPSHOT" || { echo "No snapshot found. Run 'make prod_qdrant-snapshot-export' on the server and scp it to qdrant_snapshots/"; exit 1; }; \
	echo "Restoring $$SNAPSHOT into dev collection artworks_prod_v1 (replaces existing data)..."; \
	curl -sf -X POST "http://localhost:6333/collections/artworks_prod_v1/snapshots/upload?priority=snapshot" -F "snapshot=@$$SNAPSHOT" \
		|| { echo "Restore failed (check 'make qdrant-logs'; prod and dev Qdrant versions must be compatible)"; exit 1; }; \
	echo ""
	@$(MAKE) --no-print-directory qdrant-check-vectors

qdrant-check-vectors: ## Report zero-norm vectors per museum in the dev collection
	docker compose -f docker-compose.dev.yml exec web python manage.py check_qdrant_vectors

prod_qdrant-check-vectors: ## [PROD] Report zero-norm vectors per museum in the prod collection
	docker compose -f docker-compose.prod.yml exec web python manage.py check_qdrant_vectors


# ---------- Database Utilities ---------- #

db-stop: ## Stop and remove local db container (cleanup for server)
	docker compose -f docker-compose.dev.yml stop db
	docker compose -f docker-compose.dev.yml rm -f db
