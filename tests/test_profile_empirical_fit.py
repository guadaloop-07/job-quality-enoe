"""Tests for the aggregate-only first empirical LCA candidate dossier."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from scripts.profile_empirical_fit import (
    EmpiricalFitError,
    _archive_hashes,
    _evaluation_feature_row,
    _input_sql,
    _normalized_rows,
    _renormalize_rows,
    candidate_dossier,
    final_held_out_evaluation,
    fixed_solution_robustness,
)
from scripts.profile_fitting_inputs import (
    DEVELOPMENT_PERIODS,
    EVALUATION_PERIODS,
    SELECTION_PERIODS,
)
from scripts.profile_lca import LCAFit


def _raw_row(period: str, weight: int = 1) -> dict[str, object]:
    return {
        "survey_year": int(period[:4]),
        "survey_quarter": int(period[-1]),
        "analysis_weight": weight,
        "income_band": 5,
        "income_band_state": "observed_band",
        "dur9c": "6",
        "has_health_access": True,
        "health_access_state": "observed",
        "has_other_benefits": True,
        "other_benefits_state": "observed",
        "has_written_contract": True,
        "contract_type": "indefinite",
        "contract_type_state": "observed_type",
    }


def _fit(rows, k, seed, *, categories=None):
    categories = categories or tuple(("a", "b") for _ in range(5))
    probabilities = tuple(
        np.full((k, len(feature_categories)), 1 / len(feature_categories))
        for feature_categories in categories
    )
    return (
        LCAFit(
            k,
            np.full(k, 1 / k),
            probabilities,
            categories,
            -1.0,
            True,
            1,
        ),
        32,
    )


class EmpiricalFitTests(unittest.TestCase):
    def test_primary_sql_returns_only_approved_fit_columns(self):
        query = _input_sql("primary", "selection")
        result_projection = query.split("FROM input_rows", maxsplit=1)[0]

        self.assertIn("anchored_selection", query)
        self.assertNotIn("'entity'", result_projection)
        self.assertNotIn("'n_ent'", result_projection)
        self.assertIn("source.survey_year IN (2025)", query)

    def test_primary_sql_reads_visit_sequence_from_staging(self):
        query = _input_sql("primary", "selection")
        anchored_selection, _ = query.split("), input_rows AS", maxsplit=1)

        self.assertIn("FROM staging.enoe_person_quarter AS previous", anchored_selection)
        self.assertIn("JOIN staging.enoe_person_quarter AS following", anchored_selection)
        self.assertNotIn("analysis.enoe_person_quarter_prepared AS previous", anchored_selection)

    def test_normalization_retains_only_tokens_and_quarter_normalized_weight(self):
        rows = [
            _raw_row(period, 1)
            for period in DEVELOPMENT_PERIODS + SELECTION_PERIODS
            for _ in range(2)
        ]
        normalized = _normalized_rows(rows)

        self.assertEqual(set(normalized), set(DEVELOPMENT_PERIODS + SELECTION_PERIODS))
        for period_rows in normalized.values():
            self.assertEqual(sum(row["weight"] for row in period_rows), 1.0)
            self.assertTrue(all(set(row) == {"tokens", "weight"} for row in period_rows))

    def test_complete_response_subset_is_renormalized_within_its_quarter(self):
        tokens = {
            "income_band": "income_band_5",
            "working_time_duration": "duration_6",
            "employment_health_access": "with_access",
            "non_health_benefits": "with_benefits",
            "contract_status": "indefinite",
        }
        rows = [
            {"tokens": tokens, "weight": 0.2},
            {"tokens": tokens, "weight": 0.3},
        ]

        normalized = _renormalize_rows(rows, "2023Q1")

        self.assertEqual([row["weight"] for row in normalized], [0.4, 0.6])
        self.assertEqual(sum(row["weight"] for row in normalized), 1.0)

    def test_evaluation_row_reuses_prepared_view_feature_rules(self):
        row = _evaluation_feature_row(
            {
                "survey_year": "2026",
                "survey_quarter": "1",
                "fac_tri": 250,
                "ing7c": "2",
                "hrsocup": "40",
                "dur9c": "6",
                "seg_soc": "2",
                "pre_asa": "1",
                "tip_con": "5",
            }
        )

        self.assertEqual(row["income_band_state"], "observed_band")
        self.assertEqual(row["income_band"], 2)
        self.assertFalse(row["has_health_access"])
        self.assertTrue(row["has_other_benefits"])
        self.assertFalse(row["has_written_contract"])
        self.assertEqual(row["contract_type_state"], "not_applicable")

    def test_evaluation_row_rejects_an_invalid_zero_hour_reason(self):
        with self.assertRaisesRegex(EmpiricalFitError, "zero hours"):
            _evaluation_feature_row(
                {
                    "survey_year": "2026",
                    "survey_quarter": "1",
                    "fac_tri": 250,
                    "ing7c": "2",
                    "hrsocup": "0",
                    "dur9c": "6",
                    "seg_soc": "2",
                    "pre_asa": "1",
                    "tip_con": "5",
                }
            )

    def test_final_evaluation_scores_only_the_frozen_k3_solution(self):
        core = _normalized_rows(
            [
                _raw_row(period)
                for period in DEVELOPMENT_PERIODS + SELECTION_PERIODS
                for _ in range(2)
            ]
        )
        evaluation = _normalized_rows(
            [_raw_row(period) for period in EVALUATION_PERIODS for _ in range(2)],
            EVALUATION_PERIODS,
        )
        review = {
            "selected_k": 3,
            "profile_labels": [
                {"profile_index": 1, "label": "Pattern one"},
                {"profile_index": 2, "label": "Pattern two"},
                {"profile_index": 3, "label": "Pattern three"},
            ],
        }
        score = {
            "weighted_mean_log_likelihood": -1.0,
            "posterior_weighted_profile_shares": [0.4, 0.3, 0.3],
            "unweighted_map_profile_counts": [40, 30, 30],
            "disclosure_ready": True,
        }
        with (
            patch("scripts.profile_empirical_fit.fit_multistart", side_effect=_fit),
            patch("scripts.profile_empirical_fit.score_fixed_lca", return_value=score) as scorer,
        ):
            result = final_held_out_evaluation(core, evaluation, review, 123)

        self.assertEqual(result["selected_k"], 3)
        self.assertEqual(result["evaluation_role"], "held_out_2026_only")
        self.assertEqual(set(result["evaluation_periods"]), set(EVALUATION_PERIODS))
        self.assertEqual(scorer.call_count, 2)

    def test_final_evaluation_rejects_a_reviewed_solution_other_than_k3(self):
        with self.assertRaisesRegex(EmpiricalFitError, "only for the reviewed K=3"):
            final_held_out_evaluation({}, {}, {"selected_k": 2}, 123)

    def test_candidate_dossier_is_primary_only_and_does_not_emit_raw_input_rows(self):
        normalized = {
            period: [
                {
                    "tokens": {
                        "income_band": "income_band_5",
                        "working_time_duration": "duration_6",
                        "employment_health_access": "with_access",
                        "non_health_benefits": "with_benefits",
                        "contract_status": "indefinite",
                    },
                    "weight": 0.5,
                },
                {
                    "tokens": {
                        "income_band": "income_band_1",
                        "working_time_duration": "duration_2",
                        "employment_health_access": "without_access",
                        "non_health_benefits": "without_benefits",
                        "contract_status": "without_written_contract",
                    },
                    "weight": 0.5,
                },
            ]
            for period in DEVELOPMENT_PERIODS + SELECTION_PERIODS
        }
        with patch("scripts.profile_empirical_fit.fit_multistart", side_effect=_fit):
            result = candidate_dossier(normalized, 123)

        self.assertEqual(result["selection_analysis"], "primary_only")
        self.assertEqual(result["information_criterion_winner_pending_interpretability"], 2)
        self.assertIn("conditional_response_probabilities", str(result))
        self.assertNotIn("entity", str(result))
        self.assertEqual(result["selection_status"], "awaiting_documented_interpretability_review")

    def test_archive_hashes_rejects_missing_periods(self):
        with patch("scripts.profile_empirical_fit.database_sql", return_value="{}"):
            with self.assertRaisesRegex(EmpiricalFitError, "hashes are incomplete"):
                _archive_hashes()

    def test_fixed_solution_robustness_cannot_reselect_k(self):
        normalized = {
            period: [
                {
                    "tokens": {
                        "income_band": "income_band_5",
                        "working_time_duration": "duration_6",
                        "employment_health_access": "with_access",
                        "non_health_benefits": "with_benefits",
                        "contract_status": "indefinite",
                    },
                    "weight": 0.5,
                },
                {
                    "tokens": {
                        "income_band": "income_band_1",
                        "working_time_duration": "duration_2",
                        "employment_health_access": "without_access",
                        "non_health_benefits": "without_benefits",
                        "contract_status": "without_written_contract",
                    },
                    "weight": 0.5,
                },
            ]
            for period in DEVELOPMENT_PERIODS + SELECTION_PERIODS
        }
        review = {
            "selected_k": 2,
            "plain_language_label": "Synthetic contrast",
            "substantive_dimensions": ["income_band", "contract_status"],
            "not_defined_by_response_states_alone": True,
        }
        with patch("scripts.profile_empirical_fit.fit_multistart", side_effect=_fit):
            result = fixed_solution_robustness(
                {"primary": normalized, "sensitivity_a": normalized, "sensitivity_b": normalized},
                review,
                123,
            )

        self.assertEqual(result["selected_k"], 2)
        self.assertEqual(
            set(result["robustness_only"]),
            {
                "primary",
                "sensitivity_a",
                "sensitivity_b",
                "complete_response_primary",
            },
        )
        self.assertTrue(all(item["k"] == 2 for item in result["robustness_only"].values()))


if __name__ == "__main__":
    unittest.main()
