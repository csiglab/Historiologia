PYTHON ?= python3

.PHONY: help notes-index search-index landing-metrics index check-links serve docker-build docker-up docker-down update clean

help:
	@echo "notes-index     rebuild app/note/data/index.json from app/note/data/"
	@echo "search-index    rebuild app/data/search-index.json (needs notes-index first)"
	@echo "landing-metrics rebuild app/data/landing-metrics.json (hub counts)"
	@echo "index           rebuild all indexes (notes + search + metrics)"
	@echo "check-links     report broken internal note links"
	@echo "serve           run the thin app.py server (static + read-only API)"
	@echo "docker-build    build the historiologia image"
	@echo "docker-up       start the container (PORT from .env, default 8022)"
	@echo "docker-down     stop the container"
	@echo "update          rebuild indexes + cp notes/indexes into the running container (no rebuild)"

index: notes-index search-index landing-metrics

notes-index:
	$(PYTHON) bin/build_note_index.py

search-index: notes-index
	$(PYTHON) bin/build_search_index.py

landing-metrics: notes-index
	$(PYTHON) bin/build_landing_metrics.py

check-links:
	$(PYTHON) bin/check_note_links.py

serve:
	$(PYTHON) app.py

docker-build:
	docker build -t historiologia:latest .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

# Refresh the running container with local note changes: rebuild the
# indexes, then copy the corpus + generated JSON over the container's
# app/ (rm first so renames leave no stale files). No image rebuild,
# no restart — app.py serves from disk, so the copy takes effect
# immediately. Server-code (app.py) changes still need `make docker-up`.
update: index
	@CID=$$(docker compose ps -q historiologia); \
	if [ -z "$$CID" ]; then echo "update: starting container..."; docker compose up -d >/dev/null; CID=$$(docker compose ps -q historiologia); fi; \
	if [ -z "$$CID" ]; then echo "update: container failed to start" >&2; exit 1; fi; \
	docker exec $$CID rm -rf /srv/historiologia/app/note/data /srv/historiologia/app/data; \
	docker cp ./app/note/data/. $$CID:/srv/historiologia/app/note/data/; \
	docker cp ./app/data/. $$CID:/srv/historiologia/app/data/; \
	PORT_VAL=$${PORT:-8022}; \
	curl -sf http://127.0.0.1:$$PORT_VAL/api/health -o /dev/null && echo "update: container notes refreshed ($$CID)"

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -r {} +
