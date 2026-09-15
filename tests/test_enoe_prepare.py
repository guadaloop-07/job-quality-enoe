"""Behavioral tests for the aggregate-only ENOE analytical-preparation guardrail."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.enoe_prepare import (
    CORE_PERIODS,
    PREPARATION_AUDIT_SQL,
    PreparationError,
    preparation_audit,
)


def valid_periods() -> list[dict[str, object]]:
    return [
        {
            "period": label,
            "records": 1,
            "positive_weight": 100,
            "source_archive_sha256s": ["a" * 64],
            "invalid_universe": 0,
            "invalid_income_exact": 0,
            "invalid_income_band": 0,
            "invalid_hours": 0,
            "invalid_zero_hour_reason": 0,
            "invalid_contract": 0,
            "invalid_health_access": 0,
            "invalid_other_benefits": 0,
            "unmatched_source_provenance": 0,
        }
        for label in CORE_PERIODS
    ]


class PreparationAuditTests(unittest.TestCase):
    def test_audit_returns_only_aggregate_evidence_for_the_complete_core_window(self):
        with patch(
            "scripts.enoe_prepare.database_sql",
            return_value=__import__("json").dumps(valid_periods()),
        ):
            result = preparation_audit()

        self.assertTrue(result["reconciled"])
        self.assertEqual(result["core_periods"], list(CORE_PERIODS))
        self.assertEqual(result["prepared_view"], "analysis.enoe_person_quarter_prepared")
        self.assertNotIn("ingocup", str(result))
        self.assertIn("metadata.source_archives", PREPARATION_AUDIT_SQL)

    def test_audit_rejects_an_incomplete_core_window(self):
        periods = valid_periods()[:-1]
        with patch(
            "scripts.enoe_prepare.database_sql", return_value=__import__("json").dumps(periods)
        ):
            with self.assertRaisesRegex(PreparationError, "core window is incomplete"):
                preparation_audit()

    def test_audit_fails_closed_on_invalid_zero_hour_reason(self):
        periods = valid_periods()
        periods[0]["invalid_zero_hour_reason"] = 1
        with patch(
            "scripts.enoe_prepare.database_sql", return_value=__import__("json").dumps(periods)
        ):
            with self.assertRaisesRegex(PreparationError, "invalid_zero_hour_reason=1"):
                preparation_audit()

    def test_audit_rejects_nonunique_source_provenance(self):
        periods = valid_periods()
        periods[0]["source_archive_sha256s"] = ["a" * 64, "b" * 64]
        with patch(
            "scripts.enoe_prepare.database_sql", return_value=__import__("json").dumps(periods)
        ):
            with self.assertRaisesRegex(PreparationError, "source provenance is not unique"):
                preparation_audit()


if __name__ == "__main__":
    unittest.main()
