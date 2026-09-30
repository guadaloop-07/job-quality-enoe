"""Behavioral tests for predeclared ENOE longitudinal split sensitivities."""

from __future__ import annotations

import copy
import unittest

from scripts.profile_longitudinal_sensitivities import (
    ALL_PERIODS,
    LongitudinalSensitivityError,
    audit_longitudinal_sensitivities,
    validate_sensitivity_evidence,
)


def record(period: str, visit: str, *, resident: str, weight: str = "100") -> dict[str, object]:
    return {
        "survey_year": int(period[:4]),
        "survey_quarter": int(period[-1]),
        "entity": "14",
        "cd_a": "001",
        "con": "0001",
        "v_sel": "1",
        "n_hog": "1",
        "h_mud": "0",
        "n_ren": resident,
        "n_ent": visit,
        "analysis_weight": weight,
    }


def evidence_rows(evidence: dict[str, object], mode: str, period: str) -> dict[str, object]:
    for row in evidence["periods"]:
        if row["mode"] == mode and row["period"] == period:
            return row
    raise AssertionError(f"missing {mode} {period}")


class LongitudinalSensitivityTests(unittest.TestCase):
    def baseline_records(self) -> list[dict[str, object]]:
        rows = [record(period, "1", resident=f"base_{period}") for period in ALL_PERIODS]
        rows.extend(
            [
                record("2024Q4", "2", resident="development_selection"),
                record("2025Q1", "3", resident="development_selection"),
                record("2025Q2", "4", resident="development_selection"),
                record("2025Q4", "2", resident="selection_evaluation"),
                record("2026Q1", "3", resident="selection_evaluation"),
                record("2026Q2", "4", resident="selection_evaluation"),
            ]
        )
        return rows

    def test_primary_selects_only_with_validated_boundary_anchors(self):
        evidence = validate_sensitivity_evidence(
            audit_longitudinal_sensitivities(self.baseline_records())
        )

        primary_selection = evidence_rows(evidence, "primary", "2025Q2")
        primary_evaluation = evidence_rows(evidence, "primary", "2026Q2")
        complete_selection = evidence_rows(evidence, "sensitivity_a", "2025Q2")

        self.assertEqual(
            evidence["primary_boundary_anchor_counts"],
            {
                "development_to_selection": 1,
                "selection_to_evaluation": 1,
            },
        )
        self.assertEqual(primary_selection["excluded_records"], 1)
        self.assertEqual(primary_evaluation["excluded_records"], 1)
        self.assertEqual(complete_selection["excluded_records"], 0)
        self.assertFalse(evidence["fit_authorized"])

    def test_conservative_sensitivity_excludes_all_prior_role_signature_matches(self):
        evidence = validate_sensitivity_evidence(
            audit_longitudinal_sensitivities(self.baseline_records())
        )

        conservative_selection = evidence_rows(evidence, "sensitivity_b", "2025Q2")
        conservative_evaluation = evidence_rows(evidence, "sensitivity_b", "2026Q2")

        self.assertEqual(conservative_selection["excluded_records"], 1)
        self.assertEqual(conservative_evaluation["excluded_records"], 1)
        self.assertEqual(conservative_evaluation["excluded_positive_weight"], "100")

    def test_ambiguous_or_invalid_visits_cannot_anchor_primary_exclusion(self):
        ambiguous = self.baseline_records() + [
            record("2025Q1", "3", resident="development_selection")
        ]
        evidence = validate_sensitivity_evidence(audit_longitudinal_sensitivities(ambiguous))
        self.assertEqual(evidence["primary_boundary_anchor_counts"]["development_to_selection"], 0)

        invalid = self.baseline_records()
        invalid[0]["n_ent"] = "9"
        with self.assertRaisesRegex(LongitudinalSensitivityError, "requires reload or review"):
            audit_longitudinal_sensitivities(invalid)

    def test_validation_rejects_nonreconciling_or_authorized_evidence(self):
        evidence = audit_longitudinal_sensitivities(self.baseline_records())
        nonreconciling = copy.deepcopy(evidence)
        nonreconciling["periods"][0]["excluded_records"] = 1
        authorized = copy.deepcopy(evidence)
        authorized["fit_authorized"] = True

        with self.assertRaisesRegex(LongitudinalSensitivityError, "counts do not reconcile"):
            validate_sensitivity_evidence(nonreconciling)
        with self.assertRaisesRegex(LongitudinalSensitivityError, "must not authorize"):
            validate_sensitivity_evidence(authorized)


if __name__ == "__main__":
    unittest.main()
