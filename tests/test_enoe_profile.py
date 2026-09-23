"""Behavioral tests for aggregate-only weighted ENOE classifier profiles."""

from __future__ import annotations

import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from scripts.enoe_profile import (
    CORE_PERIODS,
    MINIMUM_UNWEIGHTED_RECORDS,
    PROFILE_AUDIT_SQL,
    PROFILE_SQL,
    ProfileError,
    audit_payload,
    profile_report,
    report_payload,
)


def valid_periods() -> list[dict[str, object]]:
    return [
        {
            "period": period,
            "records": 400,
            "positive_weight": 4000,
            "invalid_weight": 0,
            "invalid_activity_branch": 0,
            "invalid_occupation_group": 0,
            "invalid_unit_size": 0,
            "invalid_employment_formality": 0,
            "invalid_informal_sector": 0,
        }
        for period in CORE_PERIODS
    ]


def cell(code: str, state: str, records: int, weight: int) -> dict[str, object]:
    return {
        "period": "2023Q1",
        "classifier": "contract_type",
        "category_code": code,
        "category_state": state,
        "unweighted_records": records,
        "weighted_records": weight,
        "denominator_unweighted_records": 400,
        "denominator_weight": 4000,
        "weighted_share": Decimal(weight) / Decimal(4000),
    }


def valid_rows() -> list[dict[str, object]]:
    return [
        cell("observed_type", "valid", 100, 1000),
        cell("unspecified", "unspecified", 100, 1000),
        cell("not_applicable", "not_applicable", 100, 1000),
        cell("<missing>", "missing", 100, 1000),
    ]


class ProfileTests(unittest.TestCase):
    def test_audit_accepts_complete_positive_weight_core_window(self):
        self.assertTrue(audit_payload(valid_periods())["profile_inputs_validated"])
        self.assertIn("analysis_weight <= 0", PROFILE_AUDIT_SQL)

    def test_audit_rejects_invalid_classifier_code(self):
        periods = valid_periods()
        periods[0]["invalid_activity_branch"] = 1
        with self.assertRaisesRegex(ProfileError, "invalid_activity_branch=1"):
            audit_payload(periods)

    def test_report_preserves_missing_unspecified_and_not_applicable_categories(self):
        report = report_payload(valid_rows())
        states = {estimate["category_state"] for estimate in report["estimates"]}

        self.assertEqual(states, {"valid", "unspecified", "not_applicable", "missing"})
        self.assertTrue(all(not estimate["suppressed"] for estimate in report["estimates"]))
        self.assertEqual(
            report["domain"], "Jalisco statewide only; municipalities are not supported domains"
        )

    def test_small_cell_is_suppressed_without_estimate_or_denominator(self):
        rows = [
            {
                **cell("temporary", "valid", MINIMUM_UNWEIGHTED_RECORDS - 1, 290),
                "denominator_unweighted_records": 100,
                "denominator_weight": 1000,
                "weighted_share": Decimal("0.29"),
            },
            {
                **cell("indefinite", "valid", 71, 710),
                "denominator_unweighted_records": 100,
                "denominator_weight": 1000,
                "weighted_share": Decimal("0.71"),
            },
        ]
        report = report_payload(rows)
        suppressed = (
            report["estimates"][1]
            if report["estimates"][0]["suppressed"] is False
            else report["estimates"][0]
        )

        self.assertTrue(suppressed["suppressed"])
        self.assertNotIn("weighted_share", suppressed)
        self.assertNotIn("denominator_weight", suppressed)

    def test_report_rejects_inconsistent_denominators(self):
        rows = valid_rows()
        rows[1]["denominator_weight"] = 3999
        with self.assertRaisesRegex(ProfileError, "inconsistent denominators"):
            report_payload(rows)

    def test_database_report_is_aggregate_only(self):
        with patch(
            "scripts.enoe_profile.database_sql",
            side_effect=[json.dumps(valid_periods()), json.dumps(valid_rows(), default=str)],
        ):
            result = profile_report()

        self.assertTrue(result["profile_inputs_validated"])
        self.assertNotIn("n_ren", json.dumps(result))
        self.assertIn("enoe_weighted_profile", PROFILE_SQL)


if __name__ == "__main__":
    unittest.main()
