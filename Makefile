# Developer shortcuts. Run `make install` once, then `make check` before pushing.
PYTHON ?= 3.11
BIN := .venv/bin

.PHONY: install lint format typecheck test check experiment model start stop

install:
	uv venv -p $(PYTHON) --allow-existing .venv
	uv pip install --python $(BIN)/python -e '.[dev]'

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

typecheck:
	$(BIN)/mypy

test:
	$(BIN)/pytest --cov=comps --cov-report=term-missing

check: lint typecheck test

# Eval: run the pipeline at COMMIT (default HEAD) as a black box over HTTP on the fixtures, score the
# captured output against golden labels, append to eval/experiments.json.
# Usage: make experiment DESC="what it tests" [COMMIT=<sha>] [MODEL=<embedding model>] [HELD_OUT=1]
experiment:
	@test -n "$$DESC" || { echo 'usage: make experiment DESC="what this run tests" [COMMIT=sha] [MODEL=name]'; exit 2; }
	$(BIN)/python eval/run.py --commit "$${COMMIT:-HEAD}" --desc "$$DESC" $${MODEL:+--set "EMBEDDING_MODEL=$$MODEL"} $${HELD_OUT:+--held-out}

# Download the configured embedding model (EMBEDDING_MODEL; default in src/comps/config.py) into MODEL_CACHE_DIR.
model:
	PYTHONPATH=src $(BIN)/python -m comps.retrieval.embedding

# Start the API (http://localhost:8000) and the web UI (http://localhost:3000) with Docker.
# Usage: make start DIR=/path/to/data [SERVICES="api web"]   (the folder must contain companies.json and
# fx_rates.json). SERVICES defaults to all; e.g. SERVICES=api starts the API only (no front end).
start:
	@scripts/start.sh "$(DIR)" $(SERVICES)

stop:
	DIR=. docker compose down
