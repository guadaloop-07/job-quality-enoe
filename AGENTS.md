# Repository instructions

## Language

Write files, code comments, commits, issues, and PRs in English. Preserve original
survey variable names and exact source titles. Conversation may follow the user's
language.

## Required Git workflow

1. Inspect the working tree and instructions; preserve unrelated changes.
2. Open or identify the issue before editing project files.
3. Create an issue-linked branch from current `main`, such as
   `chore/1-repository-bootstrap` or `feat/12-income-preparation`.
4. Implement a focused change and run relevant validation, including `just check`.
5. Commit in English with a conventional title, push, and open a PR containing
   `Closes #<issue-number>` and actual validation results.
6. Squash merge only within the user's authorized scope, after required checks
   pass and review threads are resolved.

Never push directly to `main`, bypass failing checks or hooks, weaken protection
to complete work, or use an administrator merge override. Do not open unrelated
issues. Keep the single-maintainer approval policy in repository governance.

## Code discovery

Prefer codebase-memory-mcp for code discovery. Index this repository if needed,
then use `search_graph`, `trace_path`, `get_code_snippet`, or `query_graph`.
Use text search for configuration, documentation, literal strings, or insufficient
graph results. Do not commit the local graph cache.

## Development and research

- Use Python 3.12 and uv; commit dependency changes with the lockfile.
- Shared checks: `uv run pre-commit run --all-files --hook-stage manual`.
- Add meaningful tests with behavior changes; do not create placeholder tests or
  numerical results for the infrastructure-only baseline.
- Keep microdata, credentials, notebook outputs, and model binaries out of Git.
- Record universes, missing-value rules, weights, and source versions.
- Municipal identifiers do not establish municipal representativeness.
- Analytical profiles are not official INEGI categories.

See `CONTRIBUTING.md` for details.
