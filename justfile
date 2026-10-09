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

enoe-prepare:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_prepare.py

enoe-profile:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_profile.py

enoe-baseline:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_baseline.py

enoe-evaluation-download period:
    uv run --locked python scripts/enoe_temporal_audit.py download {{period}}

enoe-evaluation-audit:
    uv run --locked python scripts/enoe_temporal_audit.py audit

profile-model-contract-validate:
    uv run --locked python scripts/profile_model_contract.py

profile-fitting-input-audit:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/profile_fitting_inputs.py audit-core

profile-fitting-evaluation-audit:
    uv run --locked python scripts/profile_fitting_inputs.py audit-evaluation

enoe-longitudinal-followup-audit:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/enoe_longitudinal_audit.py audit-core

enoe-longitudinal-followup-evaluation-audit:
    uv run --locked python scripts/enoe_longitudinal_audit.py audit-evaluation

profile-longitudinal-sensitivity-audit:
    uv run --locked python scripts/profile_longitudinal_sensitivities.py

profile-lca-synthetic-check:
    uv run --locked python scripts/profile_lca.py synthetic-check

profile-lca-candidate-dossier:
    uv run --locked python scripts/profile_empirical_fit.py candidate-dossier

profile-lca-fixed-robustness review:
    uv run --locked python scripts/profile_empirical_fit.py fixed-solution-robustness --interpretability-review {{review}}

profile-lca-final-held-out-evaluation review:
    uv run --locked python scripts/profile_empirical_fit.py final-held-out-evaluation --interpretability-review {{review}}

catalog-validate:
    uv run --locked python scripts/validate_compose_env.py >&2
    uv run --locked python scripts/catalog_validate.py
