"""Tests for the aggregate-only first empirical LCA candidate dossier."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from scripts.profile_empirical_fit import (
    EmpiricalFitError,
    _archive_hashes,
    _input_sql,
    _normalized_rows,
    candidate_dossier,
    fixed_solution_robustness,
)
from scripts.profile_fitting_inputs import DEVELOPMENT_PERIODS, SELECTION_PERIODS
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
    probabilities = tuple(np.tile((0.8, 0.2), (k, 1)) for _ in range(5))
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
