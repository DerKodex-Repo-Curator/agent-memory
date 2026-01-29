.PHONY: help install download-transcripts check-transcripts load-sample load-full load-fast load-resume load-dry-run run-backend run-frontend neo4j clean geocode-locations extract-entities

# Default target
help:
	@echo "Lenny's Memory - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install              Install all dependencies (backend + frontend)"
	@echo "  make neo4j                Start Neo4j in Docker"
	@echo "  make download-transcripts Download podcast transcript files from S3"
	@echo ""
	@echo "Data Loading:"
	@echo "  make load-sample    Load 5 sample transcripts (for testing)"
	@echo "  make load-full      Load all 299 transcripts"
	@echo "  make load-fast      Load all transcripts without entity extraction (faster)"
	@echo "  make load-resume    Resume loading (skip already loaded transcripts)"
	@echo "  make load-dry-run   Preview what would be loaded without loading"
	@echo ""
	@echo "Post-Processing:"
	@echo "  make extract-entities   Extract entities from loaded sessions"
	@echo "  make geocode-locations  Geocode Location entities (add lat/lon coordinates)"
	@echo ""
	@echo "Development:"
	@echo "  make run-backend    Start FastAPI backend (port 8000)"
	@echo "  make run-frontend   Start Next.js frontend (port 3000)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove generated files and dependencies"

# Install all dependencies
install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd frontend && npm install

# Start Neo4j
neo4j:
	docker compose up -d
	@echo "Waiting for Neo4j to start..."
	@sleep 10
	@echo "Neo4j available at http://localhost:7474"

# Environment variables to suppress warnings during loading
LOAD_ENV = PYTHONWARNINGS="ignore" HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false

# Download podcast transcript files from S3
download-transcripts:
	@python scripts/download_transcripts.py
	@echo ""
	@echo "✓ Transcripts downloaded successfully!"
	@echo "  You can now run 'make load-sample' or 'make load-full'"

# Load sample transcripts (5 files for quick testing)
# Automatically downloads transcripts if not present
load-sample: check-transcripts
	cd backend && $(LOAD_ENV) uv run python ../scripts/load_transcripts.py \
		--data-dir ../data \
		--sample 5

# Load all transcripts (full dataset)
# Automatically downloads transcripts if not present
load-full: check-transcripts
	cd backend && $(LOAD_ENV) uv run python ../scripts/load_transcripts.py \
		--data-dir ../data

# Load all transcripts without entity extraction (faster)
# Automatically downloads transcripts if not present
load-fast: check-transcripts
	cd backend && $(LOAD_ENV) uv run python ../scripts/load_transcripts.py \
		--data-dir ../data \
		--no-entities

# Resume loading (skip already loaded transcripts)
# Automatically downloads transcripts if not present
load-resume: check-transcripts
	cd backend && $(LOAD_ENV) uv run python ../scripts/load_transcripts.py \
		--data-dir ../data \
		--resume

# Preview what would be loaded (dry run)
# Automatically downloads transcripts if not present
load-dry-run: check-transcripts
	cd backend && $(LOAD_ENV) uv run python ../scripts/load_transcripts.py \
		--data-dir ../data \
		--dry-run

# Internal target: check if transcripts exist, download if not
check-transcripts:
	@if [ ! -d "data" ] || [ -z "$$(find data -name '*.txt' 2>/dev/null)" ]; then \
		echo "Transcripts not found. Downloading..."; \
		python scripts/download_transcripts.py || exit 1; \
	fi

# Extract entities from already loaded sessions (post-processing)
extract-entities:
	cd backend && $(LOAD_ENV) uv run python ../scripts/load_transcripts.py \
		--data-dir ../data \
		--extract-entities-only

# Geocode Location entities (add lat/lon coordinates)
# Uses Nominatim (OpenStreetMap) by default - rate limited to 1 req/sec
geocode-locations:
	cd backend && $(LOAD_ENV) uv run python ../scripts/geocode_locations.py

# Run backend
run-backend:
	cd backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend
run-frontend:
	cd frontend && npm run dev

# Clean up
clean:
	rm -rf backend/.venv
	rm -rf frontend/node_modules
	rm -rf frontend/.next
