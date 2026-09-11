"""Apply repository-owned PostgreSQL migrations through the local Compose service."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
BOOTSTRAP_SQL = """
CREATE SCHEMA IF NOT EXISTS metadata;
CREATE TABLE IF NOT EXISTS metadata.schema_migrations (
    version text PRIMARY KEY,
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at_utc timestamptz NOT NULL DEFAULT now()
);
"""


def migration_files() -> list[Path]:
    """Return explicitly versioned migration files in deterministic order."""
    return sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def command(env_file: Path = Path(".env"), project_name: str | None = None) -> list[str]:
    """Use the database's in-container client so no password reaches command output."""
    result = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
    ]
    if project_name:
        result.extend(["--project-name", project_name])
    result.extend(
        [
            "-f",
            "compose.yaml",
            "exec",
            "-T",
            "db",
            "sh",
            "-ec",
            'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ]
    )
    return result


def run_sql(sql: str, env_file: Path = Path(".env"), project_name: str | None = None) -> str:
    """Run SQL without echoing SQL or environment values to the terminal."""
    result = subprocess.run(
        command(env_file, project_name),
        input=sql,
        text=True,
        capture_output=True,
        check=True,
        timeout=180,
    )
    return result.stdout


def applied_migrations(
    env_file: Path = Path(".env"), project_name: str | None = None
) -> dict[str, str]:
    """Read recorded versions after bootstrapping the tracking table."""
    rows = run_sql(
        "SELECT version, checksum_sha256 FROM metadata.schema_migrations ORDER BY version;",
        env_file,
        project_name,
    )
    return dict(line.split("|", maxsplit=1) for line in rows.splitlines() if line)


def sql_literal(value: str) -> str:
    """Quote a controlled migration filename or checksum for PostgreSQL."""
    return "'" + value.replace("'", "''") + "'"


def migration_sql(path: Path, checksum: str) -> str:
    """Run one migration and record its exact content hash atomically."""
    source = path.read_text()
    return f"""BEGIN;
LOCK TABLE metadata.schema_migrations IN ACCESS EXCLUSIVE MODE;
{source}
INSERT INTO metadata.schema_migrations (version, checksum_sha256)
VALUES ({sql_literal(path.name)}, {sql_literal(checksum)});
COMMIT;
"""


def apply_migrations(env_file: Path = Path(".env"), project_name: str | None = None) -> list[str]:
    """Apply unrecorded migrations and fail closed if a recorded file changed."""
    run_sql(BOOTSTRAP_SQL, env_file, project_name)
    applied = applied_migrations(env_file, project_name)
    changes: list[str] = []
    for path in migration_files():
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        previous = applied.get(path.name)
        if previous is not None:
            if previous != checksum:
                raise RuntimeError(f"Recorded migration changed: {path.name}")
            continue
        run_sql(migration_sql(path, checksum), env_file, project_name)
        changes.append(path.name)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="show applied migration versions")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--project-name")
    args = parser.parse_args()
    if args.status:
        run_sql(BOOTSTRAP_SQL, args.env_file, args.project_name)
        for version, checksum in applied_migrations(args.env_file, args.project_name).items():
            print(f"{version} {checksum}")
        return
    changes = apply_migrations(args.env_file, args.project_name)
    if changes:
        print("Applied migrations: " + ", ".join(changes))
    else:
        print("Database migrations are current.")


if __name__ == "__main__":
    main()
