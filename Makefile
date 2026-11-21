# Developer shortcuts. Run `make install` once, then `make check` before pushing.
PYTHON ?= 3.11
BIN := .venv/bin

.PHONY: install lint format typecheck test check start stop

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

# Start the API (http://localhost:8000) and the web UI (http://localhost:3000) with Docker.
# Usage: make start DIR=/path/to/data   (the folder must contain companies.json and fx_rates.json)
start:
	@scripts/start.sh "$(DIR)"

stop:
	DIR=. docker compose down
