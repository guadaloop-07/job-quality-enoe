import argparse
import csv
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.audit_raw_joins import AuditError, Source, audit_archive, build_payload, parse_source

OFFICIAL_FIELDS = [
    "tipo",
    "mes_cal",
    "cd_a",
    "cve_ent",
    "con",
    "v_sel",
    "n_hog",
    "h_mud",
    "n_ent",
    "n_ren",
]
SDEM_FIELDS = OFFICIAL_FIELDS + [
    "r_def",
    "c_res",
    "eda",
    "clase2",
    "pos_ocu",
    "fac_tri",
    "free_text",
]


def row(entity="14", **changes):
    result = {
        "tipo": "1",
        "mes_cal": "9",
        "cd_a": "14",
        "cve_ent": entity,
        "con": "10001",
        "v_sel": "1",
        "n_hog": "1",
        "h_mud": "0",
        "n_ent": "1",
        "n_ren": "1",
        "r_def": "00",
        "c_res": "1",
        "eda": "35",
        "clase2": "1",
        "pos_ocu": "1",
        "fac_tri": "100",
        "p3i": "1",
        "free_text": "secret-marker",
    }
    result.update(changes)
    return result


def csv_bytes(fields, rows):
    with tempfile.SpooledTemporaryFile(mode="w+", newline="", encoding="latin-1") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        target.seek(0)
        return target.read().encode("latin-1")


def archive(path, sdem_rows, coe1_rows, coe2_rows, *, sdem_fields=SDEM_FIELDS):
    with ZipFile(path, "w", ZIP_DEFLATED) as target:
        target.writestr("ENOE_SDEMT325.csv", csv_bytes(sdem_fields, sdem_rows))
        target.writestr("ENOE_COE1T325.csv", csv_bytes(OFFICIAL_FIELDS + ["p3i"], coe1_rows))
        target.writestr("ENOE_COE2T325.csv", csv_bytes(OFFICIAL_FIELDS, coe2_rows))


class RawJoinAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "source.zip"

    def tearDown(self):
        self.temp_dir.cleanup()

    def source(self):
        return Source(2025, 3, self.path)

    def test_canonical_key_is_safe_but_current_etl_crosses_entities(self):
        candidate = row()
        other_entity = row(entity="13", p3i="")
        correct = row()
        archive(self.path, [candidate], [other_entity, correct], [other_entity, correct])

        result = audit_archive(self.source())

        self.assertTrue(result["official_join_safe"])
        self.assertEqual(result["coe1"]["official_join"]["unmatched_records"], 0)
        current = result["coe1"]["current_etl_join"]
        self.assertEqual(current["multiple_match_records"], 1)
        self.assertEqual(current["first_match_wrong_entity_records"], 1)
        self.assertEqual(current["first_match_blank_p3i_records"], 1)
        self.assertTrue(result["current_pipeline_risk_detected"])

    def test_storage_collision_does_not_invalidate_the_official_key(self):
        september = row()
        october = row(mes_cal="10")
        archive(self.path, [september, october], [september, october], [september, october])

        result = audit_archive(self.source())

        self.assertTrue(result["official_join_safe"])
        self.assertEqual(result["sdem"]["official_key_duplicates"]["groups"], 0)
        self.assertEqual(result["sdem"]["current_storage_key_duplicates"]["groups"], 1)

    def test_duplicate_official_coe_key_fails_closed(self):
        candidate = row()
        archive(self.path, [candidate], [candidate, candidate], [candidate])

        result = audit_archive(self.source())

        self.assertFalse(result["official_join_safe"])
        self.assertEqual(result["coe1"]["official_key_duplicates"]["groups"], 1)
        self.assertEqual(result["coe1"]["official_join"]["multiple_match_records"], 1)

    def test_missing_official_column_is_rejected(self):
        candidate = row()
        fields = [field for field in SDEM_FIELDS if field != "mes_cal"]
        archive(self.path, [candidate], [candidate], [candidate], sdem_fields=fields)

        with self.assertRaisesRegex(AuditError, "mes_cal"):
            audit_archive(self.source())

    def test_payload_is_aggregate_only(self):
        candidate = row()
        archive(self.path, [candidate], [candidate], [candidate])

        payload = build_payload([self.source()])

        self.assertNotIn("secret-marker", json.dumps(payload))
        self.assertTrue(payload["official_sources_safe_to_join"])

    def test_source_parser_rejects_an_invalid_period(self):
        self.path.touch()
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_source(f"2025Q5={self.path}")


if __name__ == "__main__":
    unittest.main()
