.PHONY: dev test lint format typecheck build migrate clean help

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev:            ## Start dev server
	uvicorn src.bootstrap.main:app --reload --host 0.0.0.0 --port 8085

test:           ## Run fast tests (excludes slow)
	python -m pytest tests/ -k "not slow" --tb=short -q

test-all:       ## Run all tests including slow
	python -m pytest tests/ --tb=short -q

test-cov:       ## Run tests with coverage
	python -m pytest tests/ -k "not slow" --cov=src --cov-report=term-missing --tb=short -q

lint:           ## Lint with ruff
	ruff check src/ tests/

format:         ## Format with ruff
	ruff format src/ tests/

typecheck:      ## Typecheck with mypy (if installed)
	mypy src/ --ignore-missing-imports || true

build:          ## Build Docker image
	docker build -t mars-noise:latest .

migrate:        ## Run Alembic migrations
	alembic upgrade head

downgrade:      ## Downgrade last migration
	alembic downgrade -1

clean:          ## Remove test DB, cache, compiled files
	rm -f test_db.sqlite3
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true