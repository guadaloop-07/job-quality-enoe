# job-quality-enoe

A reproducible, survey-aware atlas of employment-quality profiles, built from ENOE microdata.

The proposed pilot covers subordinate paid workers in Jalisco during 2023–2025,
subject to validating data coverage and comparability. Profiles are analytical
constructs, not official INEGI categories. Analytical code will be added through
scoped issues. The approved [pilot scope](docs/scope.md) retains 2023–2025 as
the core window and audits through 2026 Q2. Run the
[read-only source audit](docs/source-audit.md) before analytical preparation.
The [Gate A decision](docs/gate-a-decision.md) currently blocks modeling until
the upstream joins are repaired. See the
[variable dictionary](docs/variable-dictionary.md) and
[raw join audit](docs/raw-join-audit.md) for the supporting evidence and
reopening criteria.

## Development setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git:

```bash
uv sync --locked
uv run pre-commit install --install-hooks
uv run pre-commit run --all-files --hook-stage manual
```

Python 3.12 is selected by `.python-version`; uv can provision it if needed.
Dependencies are recorded in `uv.lock`. Install [just](https://github.com/casey/just),
then use `just setup` and `just check`. Install hooks for every new clone: Git
does not distribute installed hooks.

Hooks check file hygiene, structured-file syntax, private keys, large files,
Python lint/format, and notebook outputs. Local commits to `main` are blocked;
GitHub runs shared checks on pull requests and `main`.

## Independent local database

The project-owned PostgreSQL 17 environment is empty by design and separate from
work systems. It uses a private `.env`, a loopback-only default port of 5435,
and versioned migrations. Follow the [local database guide](docs/local-database.md)
to start it, preserve its volume, apply migrations, test it, and back it up. Run
`just --list` to see the available repository recipes.

Official source ingestion is documented separately in the
[ENOE ingestion guide](docs/official-enoe-ingestion.md). It loads only official
INEGI archives into the project-owned database; the approved archive hashes are
in the [source manifest](docs/official-enoe-source-manifest.md) and the loaded
core window has an aggregate [reconciliation table](docs/official-enoe-reconciliation.md).

## Contribution workflow

Write repository content, code comments, commits, issues, and PRs in English.
Preserve original survey field names and exact source titles when necessary.

1. Open an issue with scope, deliverable, and acceptance criteria.
2. Create a branch such as `feat/12-income-preparation` from updated `main`.
3. Implement a focused change and run the relevant checks.
4. Open a PR with `Closes #12` and accurate validation evidence.
5. Squash merge after required checks pass and review threads are resolved.

See [CONTRIBUTING.md](CONTRIBUTING.md), [agent instructions](AGENTS.md), and
[repository governance](docs/repository-governance.md).

## Data and reproducibility

Keep microdata, credentials, trained models, and unreviewed generated outputs
outside Git. Record source versions, survey definitions, exclusions, and seeds
in versioned code and documentation. Notebook outputs are stripped on commit;
export and review publication artifacts separately.

## License

Code is licensed under [MIT](LICENSE). Datasets retain their own terms and
attribution requirements.
