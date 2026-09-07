.PHONY: setup check

setup:
	uv sync --locked
	uv run pre-commit install --install-hooks

check:
	uv lock --check
	uv run --locked pre-commit run --all-files --hook-stage manual
