# Equity research platform — dev workflow.
# All targets run inside the uv-managed virtualenv.

.DEFAULT_GOAL := help
UV ?= uv
APP := equity.api.main:app
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help install lint format typecheck contracts test cov run openapi gate clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv and install runtime + dev deps
	$(UV) sync --extra dev

lint: ## Ruff lint (check only)
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

format: ## Ruff auto-format + fix
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

typecheck: ## mypy --strict + import-linter boundary contract
	$(UV) run mypy
	$(UV) run lint-imports

contracts: ## import-linter boundary contract only
	$(UV) run lint-imports

test: ## Run the offline test suite (no live-network tests)
	$(UV) run pytest -m "not live"

cov: ## Tests with coverage
	$(UV) run pytest -m "not live" --cov=equity --cov-report=term-missing

run: ## Start the FastAPI app (serves /health)
	$(UV) run uvicorn $(APP) --host $(HOST) --port $(PORT) --reload

openapi: ## Export the OpenAPI schema to openapi.json
	$(UV) run python scripts/export_openapi.py

gate: lint typecheck test ## Full quality gate (lint + typecheck + contracts + test)

clean: ## Remove caches and build artifacts
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage openapi.json
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
