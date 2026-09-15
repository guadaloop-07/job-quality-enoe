"""Synthetic source-contract tests for the independent ENOE ingestion path."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.enoe_ingest import (
    OFFICIAL_KEY,
    REQUIRED_FIELDS,
    IngestionError,
    Period,
    payload,
    transaction_sql,
    validate_archive,
)
from scripts.migrate_database import MIGRATIONS


def fields(prefix: str, entity_name: str) -> list[str]:
    return [entity_name if field == "entity" else field for field in REQUIRED_FIELDS[prefix]]


def row(
    prefix: str, entity_name: str = "ent", entity: str = "14", **changes: str
) -> dict[str, str]:
    result = {field: "1" for field in fields(prefix, entity_name)}
    result.update(
        {
            entity_name: entity,
            "tipo": "1",
            "mes_cal": "3",
            "cd_a": "14",
            "con": "1001",
            "v_sel": "1",
            "n_hog": "1",
            "h_mud": "0",
            "n_ren": "1",
        }
    )
    if prefix == "SDEM":
        result.update(
            {
                "r_def": "0",
                "c_res": "1",
                "eda": "35",
                "clase2": "1",
                "pos_ocu": "1",
                "fac_tri": "100",
            }
        )
    result.update(changes)
    return result


def csv_bytes(fieldnames: list[str], rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("latin-1")


def archive(path: Path, *, entity_name: str = "ent", sdem=None, coe1=None, coe2=None) -> None:
    sdem = [row("SDEM", entity_name)] if sdem is None else sdem
    coe1 = [row("COE1", entity_name)] if coe1 is None else coe1
    coe2 = [row("COE2", entity_name)] if coe2 is None else coe2
    with ZipFile(path, "w", ZIP_DEFLATED) as target:
        target.writestr("ENOE_SDEMT123.csv", csv_bytes(fields("SDEM", entity_name), sdem))
        target.writestr("ENOE_COE1T123.csv", csv_bytes(fields("COE1", entity_name), coe1))
        target.writestr("ENOE_COE2T123.csv", csv_bytes(fields("COE2", entity_name), coe2))


class IngestionContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "source.zip"
        self.period = Period(2023, 1)

    def tearDown(self):
        self.temporary.cleanup()

    def test_pre_2025_ent_layout_validates_and_builds_only_aggregate_payload(self):
        archive(self.path, coe1=[row("COE1", p3i="secret-marker")])
        validated = validate_archive(self.period, self.path)

        self.assertEqual(validated.audit["candidate_records"], 1)
        self.assertEqual(validated.records[0]["p3i"], "secret-marker")
        self.assertNotIn("secret-marker", json.dumps(payload(validated)))

    def test_2025_cve_ent_layout_normalizes_entity(self):
        archive(
            self.path,
            entity_name="cve_ent",
            sdem=[row("SDEM", "cve_ent")],
            coe1=[row("COE1", "cve_ent")],
            coe2=[row("COE2", "cve_ent")],
        )
        validated = validate_archive(Period(2025, 3), self.path)

        self.assertEqual(validated.records[0]["entity"], "14")

    def test_mes_cal_is_part_of_the_storage_key(self):
        march_sdem = row("SDEM", mes_cal="3")
        april_sdem = row("SDEM", mes_cal="4")
        archive(
            self.path,
            sdem=[march_sdem, april_sdem],
            coe1=[row("COE1", mes_cal="3"), row("COE1", mes_cal="4")],
            coe2=[row("COE2", mes_cal="3"), row("COE2", mes_cal="4")],
        )
        validated = validate_archive(self.period, self.path)

        self.assertEqual(len(validated.records), 2)
        self.assertIn("mes_cal", OFFICIAL_KEY)
        self.assertIn("mes_cal", transaction_sql(validated))

    def test_other_entity_cannot_supply_a_reduced_key_match(self):
        other = row("COE1", entity="13", p3i="wrong")
        archive(self.path, coe1=[other, row("COE1", p3i="correct")])
        validated = validate_archive(self.period, self.path)

        self.assertEqual(validated.records[0]["p3i"], "correct")

    def test_duplicate_official_coe_key_fails_closed(self):
        duplicate = row("COE1")
        archive(self.path, coe1=[duplicate, duplicate.copy()])

        with self.assertRaisesRegex(IngestionError, "COE1: .*duplicate"):
            validate_archive(self.period, self.path)

    def test_missing_required_column_fails_closed(self):
        sdem_fields = [field for field in fields("SDEM", "ent") if field != "mes_cal"]
        with ZipFile(self.path, "w", ZIP_DEFLATED) as target:
            target.writestr("ENOE_SDEMT123.csv", csv_bytes(sdem_fields, [row("SDEM")]))
            target.writestr("ENOE_COE1T123.csv", csv_bytes(fields("COE1", "ent"), [row("COE1")]))
            target.writestr("ENOE_COE2T123.csv", csv_bytes(fields("COE2", "ent"), [row("COE2")]))

        with self.assertRaisesRegex(IngestionError, "SDEM: missing required columns: mes_cal"):
            validate_archive(self.period, self.path)

    def test_unmatched_candidate_fails_before_any_database_transaction(self):
        archive(self.path, coe2=[])

        with self.assertRaisesRegex(
            IngestionError, "candidate COE matches are incomplete: COE1=0, COE2=1"
        ):
            validate_archive(self.period, self.path)

    def test_replacement_transaction_is_deterministic_and_reconciles_rows_and_weight(self):
        archive(self.path)
        validated = validate_archive(self.period, self.path)
        first = transaction_sql(validated)
        second = transaction_sql(validated)

        self.assertEqual(first, second)
        self.assertIn("DELETE FROM staging.enoe_person_quarter", first)
        self.assertIn("staging reconciliation failed", first)
        self.assertIn("ON CONFLICT", first)
        self.assertNotIn("ON CONFLICT DO NOTHING", first)


@unittest.skipUnless(
    os.environ.get("ENOE_TEST_POSTGRES") == "1" and shutil.which("psql"),
    "PostgreSQL integration test opt-in required",
)
class IngestionDatabaseIntegrationTests(unittest.TestCase):
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

    def test_repeated_transaction_replaces_one_period_atomically(self):
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            self.query(migration.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.zip"
            archive(source)
            validated = validate_archive(Period(2023, 1), source)
            self.query(transaction_sql(validated))
            self.query(transaction_sql(validated))
        self.assertEqual(
            self.query(
                "SELECT count(*) || '|' || coalesce(sum(fac_tri), 0) "
                "FROM staging.enoe_person_quarter "
                "WHERE survey_year = 2023 AND survey_quarter = 1;"
            ),
            "1|100.000000",
        )


if __name__ == "__main__":
    unittest.main()
