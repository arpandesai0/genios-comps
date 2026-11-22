# Developer shortcuts. Run `make install` once, then `make check` before pushing.
PYTHON ?= 3.11
BIN := .venv/bin

.PHONY: install lint format typecheck test check eval start stop

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

# Retrieval eval on the synthetic fixture (dev split); writes eval/results/retrieval_<method>_dev.json.
eval:
	PYTHONPATH=src $(BIN)/python eval/retrieval_eval.py --split dev --out eval/results/retrieval_tfidf_v1_dev.json

# Start the API (http://localhost:8000) and the web UI (http://localhost:3000) with Docker.
# Usage: make start DIR=/path/to/data   (the folder must contain companies.json and fx_rates.json)
start:
	@scripts/start.sh "$(DIR)"

stop:
	DIR=. docker compose down
