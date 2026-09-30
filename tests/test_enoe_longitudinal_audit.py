"""Behavioral tests for aggregate-only ENOE follow-up diagnostics."""

from __future__ import annotations

import copy
import unittest

from scripts.enoe_longitudinal_audit import (
    LongitudinalAuditError,
    audit_followup_records,
    validate_followup_evidence,
)


def record(period: str, visit: str | None, *, resident: str = "1") -> dict[str, object]:
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
    }


class LongitudinalFollowupAuditTests(unittest.TestCase):
    def test_adjacent_expected_visits_are_aggregate_diagnostics_not_person_linkage(self):
        periods = ("2024Q4", "2025Q1", "2025Q2")
        evidence = audit_followup_records(
            [record("2024Q4", "2"), record("2025Q1", "3"), record("2025Q2", "4")],
            periods,
        )
        result = validate_followup_evidence(evidence, periods)

        self.assertFalse(result["candidate_signature_is_approved_linkage"])
        self.assertFalse(result["leakage_exclusion_approved"])
        self.assertTrue(result["visit_metadata_complete"])
        self.assertEqual(result["transitions"][0]["expected_next_visit_signatures"], 1)
        self.assertEqual(result["role_boundaries"][0]["from_role"], "development")
        self.assertEqual(result["role_boundaries"][0]["to_role"], "selection")

    def test_selection_to_evaluation_boundary_reports_visit_mismatch_without_keys(self):
        periods = ("2025Q4", "2026Q1", "2026Q2")
        evidence = audit_followup_records(
            [record("2025Q4", "2"), record("2026Q1", "4"), record("2026Q2", "5")],
            periods,
        )
        result = validate_followup_evidence(evidence, periods)

        self.assertEqual(result["role_boundaries"][0]["to_role"], "evaluation")
        self.assertEqual(result["transitions"][0]["mismatched_visit_signatures"], 1)
        self.assertEqual(result["transitions"][1]["expected_next_visit_signatures"], 1)

    def test_missing_or_invalid_visit_metadata_blocks_an_exclusion_policy(self):
        periods = ("2024Q4", "2025Q1")
        evidence = audit_followup_records([record("2024Q4", None), record("2025Q1", "6")], periods)
        result = validate_followup_evidence(evidence, periods)

        self.assertFalse(result["visit_metadata_complete"])
        self.assertEqual(result["periods"][0]["missing_visit_records"], 1)
        self.assertEqual(result["periods"][1]["invalid_visit_records"], 1)
        self.assertTrue(result["blocking_reasons"])

    def test_ambiguous_candidate_signature_is_reported_and_not_used_for_transition(self):
        periods = ("2024Q4", "2025Q1")
        evidence = audit_followup_records(
            [
                record("2024Q4", "2"),
                record("2024Q4", "2"),
                record("2025Q1", "3"),
            ],
            periods,
        )
        result = validate_followup_evidence(evidence, periods)

        self.assertEqual(result["periods"][0]["ambiguous_signature_groups"], 1)
        self.assertEqual(result["transitions"][0]["unambiguous_shared_signatures"], 0)

    def test_approved_person_linkage_or_unexpected_periods_fail_closed(self):
        periods = ("2024Q4", "2025Q1")
        evidence = audit_followup_records([record("2024Q4", "2"), record("2025Q1", "3")], periods)
        unsafe = copy.deepcopy(evidence)
        unsafe["candidate_signature_is_approved_linkage"] = True

        with self.assertRaisesRegex(LongitudinalAuditError, "must not be treated"):
            validate_followup_evidence(unsafe, periods)
        with self.assertRaisesRegex(LongitudinalAuditError, "outside the requested audit"):
            audit_followup_records([record("2026Q1", "1")], periods)


if __name__ == "__main__":
    unittest.main()
