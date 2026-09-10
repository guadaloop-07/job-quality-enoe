"""Run aggregate SQL in one read-only PostgreSQL snapshot."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(env: dict[str, str]) -> list[str]:
    """Use libpq locally or the existing container's database role."""
    container = env.get("ENOE_DOCKER_CONTAINER")
    database = env.get("PGDATABASE", "enoe_microdatos")
    if container:
        return [
            "docker",
            "exec",
            "-i",
            container,
            "sh",
            "-c",
            'exec psql -U "$POSTGRES_USER" -d "$1" -X -qAt -v ON_ERROR_STOP=1',
            "audit",
            database,
        ]
    return ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", database]


def run_query(sql: str, env: dict[str, str] | None = None) -> dict:
    env = dict(os.environ if env is None else env)
    transaction = (
        "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
        "SET LOCAL statement_timeout = '60s';\n" + sql + "\nCOMMIT;\n"
    )
    result = subprocess.run(
        command(env),
        input=transaction,
        text=True,
        capture_output=True,
        env=env,
        timeout=180,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sql = (ROOT / "sql" / "source_audit.sql").read_text()
    payload = run_query(sql)
    payload["provenance"] = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "source_relation": "public.stg_enoe_microdatos",
        "scope": "2023-Q1 through 2026-Q2; candidate universe is provisional",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents replacing previous evidence.
    with args.output.open("x") as output:
        json.dump(payload, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
