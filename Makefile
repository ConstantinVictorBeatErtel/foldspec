.PHONY: setup dev frontend backend contracts

setup:
	uv python install 3.12
	uv sync --python 3.12
	cd apps/web && pnpm install
	uv run python scripts/generate_contracts.py
	@if [ ! -f .env ]; then cp .env.example .env; chmod 600 .env; fi

contracts:
	uv run python scripts/generate_contracts.py

frontend:
	cd apps/web && pnpm dev

backend:
	uv run uvicorn services.api.main:app --reload --host 127.0.0.1 --port 8000

dev:
	@echo "Run 'make frontend' and 'make backend' in separate terminals."
