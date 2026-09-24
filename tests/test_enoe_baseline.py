"""Behavioral tests for the aggregate-only ENOE descriptive baseline."""

from __future__ import annotations

import unittest
from decimal import Decimal

from scripts.enoe_baseline import (
    BASELINE_CLASSIFIERS,
    CORE_PERIODS,
    BaselineError,
    baseline_payload,
    render_markdown,
)


def profile_fixture() -> dict[str, object]:
    estimates = []
    for classifier in BASELINE_CLASSIFIERS:
        for period in CORE_PERIODS:
            for code, share in (("1", Decimal("0.6")), ("2", Decimal("0.4"))):
                estimates.append(
                    {
                        "period": period,
                        "classifier": classifier,
                        "category_code": code,
                        "category_state": "valid",
                        "suppressed": False,
                        "unweighted_records": "240",
                        "weighted_records": str(share * 4000),
                        "denominator_unweighted_records": "400",
                        "denominator_weight": "4000",
                        "weighted_share": str(share),
                    }
                )
    return {
        "profile_inputs_validated": True,
        "source": "repository-owned official ENOE staging",
        "unit_of_analysis": "person-quarter",
        "domain": "Jalisco statewide only; municipalities are not supported domains",
        "weight_rule": "analysis_weight > 0; FAC_TRI is used within each survey quarter",
        "core_periods": list(CORE_PERIODS),
        "estimates": estimates,
    }


class BaselineTests(unittest.TestCase):
    def test_baseline_builds_all_classifier_timelines(self):
        baseline = baseline_payload(profile_fixture())

        self.assertEqual(len(baseline["timelines"]), len(BASELINE_CLASSIFIERS))
        self.assertTrue(
            all(len(timeline["cells"]) == len(CORE_PERIODS) for timeline in baseline["timelines"])
        )
        self.assertEqual(baseline["timelines"][0]["cells"][0]["weighted_share"], Decimal("0.6"))

    def test_baseline_rejects_an_incomplete_core_window(self):
        profile = profile_fixture()
        profile["core_periods"] = list(CORE_PERIODS[:-1])

        with self.assertRaisesRegex(BaselineError, "complete 2023Q1--2025Q4"):
            baseline_payload(profile)

    def test_baseline_rejects_a_classifier_period_without_visible_estimates(self):
        profile = profile_fixture()
        for estimate in profile["estimates"]:
            if estimate["period"] == "2023Q1" and estimate["classifier"] == "income_band":
                estimate["suppressed"] = True
                for field in (
                    "unweighted_records",
                    "weighted_records",
                    "denominator_unweighted_records",
                    "denominator_weight",
                    "weighted_share",
                ):
                    estimate.pop(field)

        with self.assertRaisesRegex(BaselineError, "no disclosure-eligible"):
            baseline_payload(profile)

    def test_markdown_keeps_informal_classifiers_distinct(self):
        report = render_markdown(baseline_payload(profile_fixture()))

        self.assertIn("| employment_formality |", report)
        self.assertIn("| informal_sector |", report)
        self.assertIn("it does not pool person-quarters", report)
        self.assertNotIn("n_ren", report)


if __name__ == "__main__":
    unittest.main()
