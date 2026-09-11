.PHONY: setup check db-up db-status db-migrate db-migration-status db-test db-down db-config

setup:
	uv sync --locked
	uv run pre-commit install --install-hooks

check:
	uv lock --check
	uv run --locked pre-commit run --all-files --hook-stage manual
	uv run --locked python -m unittest discover -s tests -v

db-up:
	uv run --locked python scripts/validate_compose_env.py
	docker compose --env-file .env -f compose.yaml up -d db

db-status:
	uv run --locked python scripts/validate_compose_env.py
	docker compose --env-file .env -f compose.yaml ps

db-migrate:
	uv run --locked python scripts/validate_compose_env.py
	uv run --locked python scripts/migrate_database.py

db-migration-status:
	uv run --locked python scripts/validate_compose_env.py
	uv run --locked python scripts/migrate_database.py --status

db-test:
	uv run --locked python scripts/validate_compose_env.py
	uv run --locked python scripts/check_local_database.py

db-down:
	uv run --locked python scripts/validate_compose_env.py
	docker compose --env-file .env -f compose.yaml down

db-config:
	uv run --locked python scripts/validate_compose_env.py
	docker compose --env-file .env -f compose.yaml config --no-interpolate
