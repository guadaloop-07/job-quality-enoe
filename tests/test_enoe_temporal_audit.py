"""Synthetic contracts for the separate ENOE 2026 temporal-evaluation audit."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.enoe_ingest import Period
from scripts.enoe_temporal_audit import (
    EVALUATION_PERIODS,
    REFERENCE_PERIOD,
    TemporalAuditError,
    audit_temporal_evaluation,
    parse_evaluation_period,
)
from tests.test_enoe_ingest import archive, row


class TemporalAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.reference = self.directory / REFERENCE_PERIOD.archive_name
        archive(self.reference)
        self.evaluation = {}
        for period in EVALUATION_PERIODS:
            path = self.directory / period.archive_name
            archive(path, entity_name="cve_ent")
            self.evaluation[period] = path

    def tearDown(self):
        self.temporary.cleanup()

    def test_audit_accepts_complete_2026_archives_without_loading_staging(self):
        result = audit_temporal_evaluation(self.reference, self.evaluation)

        self.assertEqual(
            result["decision"], "source_integrity_passed_for_separate_temporal_evaluation"
        )
        self.assertEqual(result["reference_period"], "2025Q4")
        self.assertEqual(
            [period["period"] for period in result["evaluation_periods"]], ["2026Q1", "2026Q2"]
        )
        self.assertEqual(result["evaluation_periods"][0]["invalid_codes"]["ing7c"], 0)
        self.assertTrue(
            result["evaluation_periods"][0]["schema_comparison_to_2025Q4"]["SDEM"][
                "required_fields_present"
            ]
        )

    def test_audit_rejects_invalid_classifier_codes(self):
        period = Period(2026, 1)
        archive(
            self.evaluation[period],
            entity_name="cve_ent",
            sdem=[row("SDEM", "cve_ent", ing7c="8")],
            coe1=[row("COE1", "cve_ent")],
            coe2=[row("COE2", "cve_ent")],
        )

        with self.assertRaisesRegex(TemporalAuditError, "invalid codes: ing7c"):
            audit_temporal_evaluation(self.reference, self.evaluation)

    def test_audit_requires_both_evaluation_periods(self):
        with self.assertRaisesRegex(TemporalAuditError, "exactly 2026Q1 and 2026Q2"):
            audit_temporal_evaluation(
                self.reference, {Period(2026, 1): self.evaluation[Period(2026, 1)]}
            )

    def test_parser_rejects_core_periods(self):
        self.assertEqual(parse_evaluation_period("2026Q2"), Period(2026, 2))
        with self.assertRaisesRegex(Exception, "2026Q1 or 2026Q2"):
            parse_evaluation_period("2025Q4")


if __name__ == "__main__":
    unittest.main()
