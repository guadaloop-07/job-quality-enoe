set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set dotenv-load := false

default: check

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

enoe-download period:
    uv run --locked python scripts/enoe_ingest.py download {{period}}

enoe-validate period archive:
    uv run --locked python scripts/enoe_ingest.py validate {{period}} --archive {{archive}}

enoe-ingest period archive:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_ingest.py ingest {{period}} --archive {{archive}}

enoe-ingest-all:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_ingest.py ingest-all

enoe-audit period archive:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_ingest.py audit-staging {{period}} --archive {{archive}}

enoe-audit-all:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_ingest.py audit-all

enoe-status:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_ingest.py status

enoe-manifest:
    uv run --locked python scripts/enoe_ingest.py manifest
