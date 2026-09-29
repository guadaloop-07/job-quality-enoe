"""Behavioral tests for guarded, pre-fit ENOE profile inputs."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.profile_fitting_inputs import (
    AUDIT_FIELDS,
    DEVELOPMENT_PERIODS,
    SELECTION_PERIODS,
    FittingInputError,
    audit_encoded_rows,
    encode_feature_row,
    evaluation_input_audit,
    validate_core_audit,
    validate_repeat_overlap,
)


def input_row(year: int = 2023, quarter: int = 1) -> dict[str, object]:
    return {
        "survey_year": year,
        "survey_quarter": quarter,
        "analysis_weight": "200.0",
        "income_band": 2,
        "income_band_state": "observed_band",
        "dur9c": "6",
        "has_health_access": True,
        "health_access_state": "observed",
        "has_other_benefits": False,
        "other_benefits_state": "observed",
        "has_written_contract": True,
        "contract_type": "indefinite",
        "contract_type_state": "observed_type",
    }


def period_rows() -> list[dict[str, object]]:
    rows = []
    for period in DEVELOPMENT_PERIODS + SELECTION_PERIODS:
        rows.append(input_row(int(period[:4]), int(period[-1])))
    return rows


def core_period_audit() -> list[dict[str, object]]:
    return [
        {
            "period": period,
            "records": 10,
            "positive_weight": 1000,
            **{field: 0 for field in AUDIT_FIELDS},
        }
        for period in DEVELOPMENT_PERIODS + SELECTION_PERIODS
    ]


class ProfileFittingInputTests(unittest.TestCase):
    def test_encoder_preserves_contract_feature_tokens_and_metadata(self):
        encoded = encode_feature_row(input_row())

        self.assertEqual(encoded["period"], "2023Q1")
        self.assertEqual(encoded["period_role"], "development")
        self.assertEqual(
            encoded["tokens"],
            {
                "income_band": "income_band_2",
                "working_time_duration": "duration_6",
                "employment_health_access": "with_access",
                "non_health_benefits": "without_benefits",
                "contract_status": "indefinite",
            },
        )

    def test_encoder_rejects_prohibited_or_inconsistent_inputs(self):
        prohibited = input_row()
        prohibited["emp_ppal"] = "2"
        inconsistent = input_row()
        inconsistent["income_band_state"] = "missing"

        with self.assertRaisesRegex(FittingInputError, "input columns differ"):
            encode_feature_row(prohibited)
        with self.assertRaisesRegex(FittingInputError, "income band conflicts"):
            encode_feature_row(inconsistent)

    def test_encoder_preserves_non_substantive_response_states(self):
        row = input_row()
        row.update(
            {
                "income_band": None,
                "income_band_state": "unspecified",
                "dur9c": None,
                "has_health_access": None,
                "health_access_state": "missing",
                "has_other_benefits": None,
                "other_benefits_state": "unspecified",
                "has_written_contract": None,
                "contract_type": None,
                "contract_type_state": "missing",
            }
        )

        tokens = encode_feature_row(row)["tokens"]

        self.assertEqual(tokens["income_band"], "unspecified")
        self.assertEqual(tokens["working_time_duration"], "missing")
        self.assertEqual(tokens["employment_health_access"], "missing")
        self.assertEqual(tokens["non_health_benefits"], "unspecified")
        self.assertEqual(tokens["contract_status"], "missing")

    def test_audit_normalizes_weight_within_each_complete_core_period(self):
        result = audit_encoded_rows(period_rows())

        self.assertFalse(result["fit_authorized"])
        self.assertEqual(len(result["periods"]), 12)
        self.assertTrue(all(period["normalized_weight_sum"] == "1" for period in result["periods"]))

    def test_audit_rejects_incomplete_or_evaluation_training_inputs(self):
        with self.assertRaisesRegex(FittingInputError, "incomplete or unexpected"):
            audit_encoded_rows(period_rows()[:-1])
        with self.assertRaisesRegex(FittingInputError, "outside the model contract"):
            encode_feature_row(input_row(2027, 1))
        with self.assertRaisesRegex(FittingInputError, "incomplete or unexpected"):
            audit_encoded_rows(period_rows() + [input_row(2026, 1)])

    def test_core_aggregate_audit_rejects_invalid_tokens(self):
        invalid = core_period_audit()
        invalid[0]["invalid_contract_status"] = 1

        with self.assertRaisesRegex(FittingInputError, "invalid_contract_status=1"):
            validate_core_audit(invalid)

    def test_repeat_overlap_remains_diagnostic_not_approved_linkage(self):
        overlap = {
            "candidate_signature": "entity_cd_a_con_v_sel_n_hog_h_mud_n_ren",
            "candidate_signature_is_approved_linkage": False,
            "development_distinct_signatures": 20,
            "selection_distinct_signatures": 10,
            "cross_role_candidate_signature_overlap": 3,
            "non_temporal_resampling": "prohibited_until_repeat_observation_audit",
        }

        result = validate_repeat_overlap(overlap)
        unsafe = copy.deepcopy(overlap)
        unsafe["candidate_signature_is_approved_linkage"] = True

        self.assertEqual(result["cross_role_candidate_signature_overlap"], 3)
        with self.assertRaisesRegex(FittingInputError, "must not be treated"):
            validate_repeat_overlap(unsafe)

    def test_evaluation_interface_requires_audited_2026_archives(self):
        evidence = {
            "decision": "source_integrity_passed_for_separate_temporal_evaluation",
            "reference_period": "2025Q4",
            "evaluation_periods": [
                {
                    "period": "2026Q1",
                    "candidate_records": 100,
                    "provenance": {"sha256": "a" * 64},
                },
                {
                    "period": "2026Q2",
                    "candidate_records": 100,
                    "provenance": {"sha256": "b" * 64},
                },
            ],
        }
        with patch(
            "scripts.profile_fitting_inputs.audit_temporal_evaluation", return_value=evidence
        ):
            result = evaluation_input_audit(Path("reference.zip"), {})

        self.assertEqual(result["input_role"], "held_out_evaluation_only")
        self.assertFalse(result["fit_authorized"])


if __name__ == "__main__":
    unittest.main()
