# Common development tasks. Run `make` or `make help` to list them.

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help setup lint fmt typecheck test cov bench build exe docs docs-serve docker clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-11s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .venv and install the package with dev and docs extras
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev,docs]" build pre-commit
	$(BIN)/pre-commit install

lint: ## Run ruff lint and format checks
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

fmt: ## Format the code and apply safe lint fixes
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

typecheck: ## Run mypy in strict mode
	$(BIN)/mypy

test: ## Run the test suite with coverage
	$(BIN)/pytest --cov --cov-report=term-missing --cov-fail-under=85

bench: ## Run the benchmarks and compare them with the committed baseline
	$(BIN)/pytest tests/test_bench.py --benchmark-enable --benchmark-only \
		--benchmark-json=bench.json
	$(BIN)/python scripts/check_bench.py bench.json benchmarks/baseline.json

build: ## Build the wheel and sdist into dist/
	$(BIN)/python -m build

exe: ## Build a standalone executable for this machine into dist/
	$(BIN)/pip install pyinstaller tzdata
	$(BIN)/python packaging/build_exe.py care-voice-local

docs: ## Build the documentation site into site/
	$(BIN)/python scripts/gen_cli_docs.py
	$(BIN)/mkdocs build --strict

docs-serve: ## Serve the documentation site with live reload
	$(BIN)/mkdocs serve

docker: ## Build the container image as care-voice:local
	docker build -t care-voice:local .

clean: ## Remove build artifacts and caches
	rm -rf build dist site bench.json .coverage coverage.xml .pytest_cache .mypy_cache .ruff_cache
