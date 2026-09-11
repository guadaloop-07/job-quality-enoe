"""Confirm migrations and the repository-owned database connection contract."""

from __future__ import annotations

import subprocess
from argparse import ArgumentParser
from pathlib import Path

from migrate_database import apply_migrations, command


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--project-name")
    args = parser.parse_args()
    apply_migrations(args.env_file, args.project_name)
    result = subprocess.run(
        command(args.env_file, args.project_name),
        input=(
            "SELECT current_database() <> '' "
            "AND to_regnamespace('metadata') IS NOT NULL "
            "AND to_regnamespace('staging') IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM metadata.schema_migrations);\n"
        ),
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )
    if result.stdout.strip() != "t":
        raise RuntimeError("Local database did not satisfy the migration connection contract.")
    print("Local database migration and connection checks passed.")


if __name__ == "__main__":
    main()
