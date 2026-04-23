.PHONY: help install lint format test smoke coverage clean docker-build docker-up

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package with dev dependencies
	pip install -e ".[dev]"

lint: ## Run ruff linter
	ruff check .

format: ## Run ruff formatter
	ruff format .

format-check: ## Check formatting without modifying files
	ruff format --check .

typecheck: ## Run mypy type checker
	mypy .

test: ## Run pytest unit tests
	python -m pytest -q

coverage: ## Run tests with coverage report
	python -m pytest --cov=gitlab --cov=services --cov=tools --cov-report=term-missing --cov-report=html

smoke: ## Run smoke tests (no live GitLab needed)
	python run_tests.py

check: lint format-check typecheck test smoke ## Run full check suite (lint + format + types + tests + smoke)

clean: ## Remove build artifacts
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov dist build *.egg-info

docker-build: ## Build Docker image
	docker compose build

docker-up: ## Start Docker containers
	docker compose up -d
