# Contributing

## Language and scope

Use English for repository content, comments, commits, issues, and pull requests.
Preserve original survey variable names and exact source citations.

Start every change with an issue. Prefer about one hour of active work per task,
with a concrete deliverable and acceptance criteria. Split larger work into
linked tasks. Dependency update PRs also need a tracking issue before merging.

## Issue → branch → pull request

```bash
git switch main
git pull --ff-only
gh issue create
git switch -c feat/12-short-description
```

Use `feat/`, `fix/`, `docs/`, `chore/`, or `refactor/`, followed by the issue number
and an English description. Do not develop directly on `main`.

Use conventional commit and PR titles, such as `chore: configure development
tooling`, `feat: prepare real monthly income`, or `fix: preserve survey join keys`.
Preserve unrelated work and keep the PR focused.

Before committing, run:

```bash
uv sync --locked
make check
git diff --check
```

Run meaningful tests for behavior changes. Add analytical tests to CI when the
corresponding code is implemented; the initial quality job does not validate
survey estimates or models. Hooks may edit files: inspect and stage those edits,
then rerun checks. Do not bypass a failing hook.

Push the branch and open a PR targeting `main`. Include `Closes #<issue-number>`,
the resulting behavior, checks actually run, and limitations. Use a draft PR
while work is incomplete. Do not claim a check passed without running it.

Squash merge only after the required `Quality` check passes, the branch is current
with `main`, and review conversations are resolved. GitHub deletes the remote
branch after merge. Update local `main` with `git pull --ff-only`; remove local
branches only after confirming their work is merged and the working tree is clean.

Issue linkage and English are review requirements, not automated language or
issue validation. GitHub enforces the protected-branch rules documented in
[repository governance](docs/repository-governance.md).

## Development tools

Run `make setup` for each clone. `make check` runs shared manual-stage checks,
including in CI. The branch guard runs only at the `pre-commit` stage, allowing
checks on unchanged `main` while rejecting direct commits. GitHub independently
requires PRs, including for administrators.

Use `uv add --dev <tool>` and commit `pyproject.toml` with `uv.lock`. Update hooks
with `uv run pre-commit autoupdate` on an issue branch. Dependabot proposes weekly
GitHub Actions and uv dependency updates; hook revisions and the CI uv version
are reviewed separately. Nothing auto-merges dependency updates.

## Research changes

- Keep microdata, credentials, model binaries, and notebook outputs outside Git.
- Record input hashes, source versions, transformations, and seeds.
- Distinguish missing, unknown, and not-applicable responses.
- Define populations, denominators, survey weights, and uncertainty.
- Describe profiles as analytical constructs, not official categories.
- Test joins, recoding, weights, and denominators when those behaviors are added.
