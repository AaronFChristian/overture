.PHONY: install up down test lint typecheck verify

install:
	uv sync --all-extras

up:
	docker compose up -d
	@echo "Waiting for Postgres to be healthy..."
	@until docker compose ps db | grep -q "healthy"; do sleep 1; done
	@echo "Postgres is up on localhost:5432"

down:
	docker compose down

test:
	uv run pytest -v

lint:
	uv run ruff check .

typecheck:
	uv run mypy src

verify: lint typecheck test
	@echo "All checks passed."
