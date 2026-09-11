"""Test local database configuration and the first migration's schema contract."""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.migrate_database import MIGRATIONS, command, migration_files
from scripts.validate_compose_env import TEMPLATE_PASSWORD, validate

ROOT = Path(__file__).resolve().parents[1]


class LocalConfigurationTests(unittest.TestCase):
    def test_compose_binds_only_to_loopback_and_uses_postgres_17(self):
        compose = (ROOT / "compose.yaml").read_text()
        self.assertIn("name: job-quality-enoe", compose)
        self.assertIn("image: postgres:17", compose)
        self.assertIn('"127.0.0.1:${POSTGRES_PORT:-5435}:5432"', compose)
        self.assertNotIn("container_name:", compose)
        self.assertIn("postgres_data:/var/lib/postgresql/data", compose)

    def test_template_password_is_rejected_without_printing_it(self):
        path = ROOT / ".env.example"
        errors = validate(path)
        self.assertTrue(errors)
        self.assertTrue(any("template value" in error for error in errors))
        self.assertTrue(all(TEMPLATE_PASSWORD not in error for error in errors))

    def test_initial_migration_has_metadata_and_staging_schemas(self):
        migrations = migration_files()
        self.assertEqual(
            [path.name for path in migrations],
            ["0001_metadata_and_staging.sql", "0002_enoe_person_quarter_staging.sql"],
        )
        source = (MIGRATIONS / migrations[0].name).read_text()
        self.assertIn("CREATE SCHEMA IF NOT EXISTS metadata", source)
        self.assertIn("CREATE SCHEMA IF NOT EXISTS staging", source)
        self.assertIn("metadata.source_archives", source)
        self.assertIn("metadata.ingestion_runs", source)
        ingestion = (MIGRATIONS / migrations[1].name).read_text()
        self.assertIn("staging.enoe_person_quarter", ingestion)
        self.assertIn("mes_cal", ingestion)

    def test_migration_command_keeps_password_out_of_arguments(self):
        args = command(Path("private.env"), "isolated-test")
        self.assertIn("private.env", args)
        self.assertIn("isolated-test", args)
        self.assertNotIn("POSTGRES_PASSWORD", " ".join(args))


@unittest.skipUnless(
    os.environ.get("ENOE_TEST_POSTGRES") == "1" and shutil.which("psql"),
    "PostgreSQL integration test opt-in required",
)
class MigrationIntegrationTests(unittest.TestCase):
    def query(self, sql: str) -> str:
        result = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", os.environ["PGDATABASE"]],
            input=sql,
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
        )
        return result.stdout.strip()

    def test_initial_migration_is_idempotent(self):
        for migration_path in migration_files():
            migration = migration_path.read_text()
            self.query(migration)
            self.query(migration)
        result = self.query(
            "SELECT to_regclass('metadata.source_archives') IS NOT NULL "
            "AND to_regclass('metadata.ingestion_runs') IS NOT NULL "
            "AND to_regclass('staging.enoe_person_quarter') IS NOT NULL;"
        )
        self.assertEqual(result, "t")
