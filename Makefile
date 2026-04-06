.PHONY: up down test lint migrate seed logs build shell

# --- Environment ---
COMPOSE = docker compose
APP_SERVICE = api
WORKER_SERVICE = worker

up:
	$(COMPOSE) up -d --build
	@echo "✅ GeoTrade stack is up. API: http://localhost:8000 | Flower: http://localhost:5555"

down:
	$(COMPOSE) down -v

build:
	$(COMPOSE) build --no-cache

migrate:
	$(COMPOSE) exec $(APP_SERVICE) alembic upgrade head

seed:
	$(COMPOSE) exec $(APP_SERVICE) python scripts/seed.py

logs:
	$(COMPOSE) logs -f --tail=100

shell:
	$(COMPOSE) exec $(APP_SERVICE) bash

# --- Local dev (no docker) ---
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker-local:
	celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 -Q ingestion,nlp,gti,default

migrate-local:
	alembic upgrade head

# --- Testing ---
test:
	pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-contract:
	pytest tests/contract/ -v

test-load:
	pytest tests/load/ -v -s

# --- Code quality ---
lint:
	ruff check app/ tests/ --fix
	ruff format app/ tests/
	mypy app/ --ignore-missing-imports

format:
	ruff format app/ tests/

typecheck:
	mypy app/

# --- Alembic ---
revision:
	alembic revision --autogenerate -m "$(message)"

downgrade:
	alembic downgrade -1

# --- Cleanup ---
clean:
	find . -type d -name __pycache__ | xargs rm -rf
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
