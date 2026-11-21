# Developer shortcuts. Run `make install` once, then `make check` before pushing.
PYTHON ?= 3.11
BIN := .venv/bin

.PHONY: install lint format typecheck test check

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
