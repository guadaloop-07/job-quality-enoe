"""Tests for the synthetic-only weighted categorical LCA engine."""

from __future__ import annotations

import unittest

import numpy as np

from scripts.profile_lca import (
    LCAError,
    LCAFit,
    aligned_stability,
    category_definitions,
    disclosure_ready,
    fit_multistart,
    fit_weighted_lca,
    select_candidate,
    synthetic_check,
    synthetic_rows,
)


class ProfileLCATests(unittest.TestCase):
    def test_synthetic_multistart_converges_without_authorizing_a_fit(self):
        fit, converged_starts = fit_multistart(synthetic_rows(), 2, 20260930)

        self.assertTrue(fit.converged)
        self.assertGreater(converged_starts, 0)
        self.assertEqual(aligned_stability(fit, fit), 1.0)
        self.assertTrue(
            all(
                np.max(parameters, axis=1).min() > 0.99
                for parameters in fit.conditional_probabilities
            )
        )
        self.assertEqual(synthetic_check()["input"], "synthetic_only")
        self.assertFalse(synthetic_check()["fit_authorized"])

    def test_rows_cannot_include_raw_identifiers_or_nonpositive_weights(self):
        invalid = synthetic_rows()[:1]
        invalid[0]["entity"] = "14"

        with self.assertRaisesRegex(LCAError, "only tokens and weight"):
            fit_weighted_lca(invalid, 2, 1)

        invalid = synthetic_rows()[:1]
        invalid[0]["weight"] = 0
        with self.assertRaisesRegex(LCAError, "weight must be positive"):
            fit_weighted_lca(invalid, 2, 1)

    def test_convergence_is_reported_when_iteration_budget_is_exhausted(self):
        fit = fit_weighted_lca(synthetic_rows(), 2, 1, max_iterations=1)

        self.assertFalse(fit.converged)
        self.assertEqual(fit.iterations, 1)

    def test_stability_aligns_equivalent_permuted_class_labels(self):
        categories = tuple(("a", "b") for _ in range(5))
        parameters = tuple(np.asarray(((0.9, 0.1), (0.2, 0.8))) for _ in range(5))
        reference = LCAFit(
            2,
            np.asarray((0.6, 0.4)),
            parameters,
            categories,
            0.0,
            True,
            1,
        )
        permuted = LCAFit(
            2,
            np.asarray((0.4, 0.6)),
            tuple(feature[::-1] for feature in parameters),
            categories,
            0.0,
            True,
            1,
        )

        self.assertEqual(aligned_stability(reference, permuted), 1.0)

    def test_shared_category_definitions_align_fits_with_an_absent_quarterly_token(self):
        rows = synthetic_rows()
        categories = category_definitions(rows)
        reference = fit_weighted_lca(rows, 2, 1, categories=categories, max_iterations=1)
        comparison = fit_weighted_lca(
            [row for row in rows if row["tokens"]["income_band"] != "income_band_5"],
            2,
            2,
            categories=categories,
            max_iterations=1,
        )

        self.assertEqual(reference.categories, comparison.categories)
        self.assertIsInstance(aligned_stability(reference, comparison), float)

    def test_selection_uses_gates_in_predeclared_order(self):
        diagnostics = [
            {
                "k": 2,
                "converged": False,
                "stability": 1.0,
                "weighted_shares": (0.5, 0.5),
                "information_criterion": 1.0,
                "interpretable": True,
            },
            {
                "k": 3,
                "converged": True,
                "stability": 0.79,
                "weighted_shares": (0.4, 0.3, 0.3),
                "information_criterion": 2.0,
                "interpretable": True,
            },
            {
                "k": 4,
                "converged": True,
                "stability": 0.9,
                "weighted_shares": (0.4, 0.3, 0.26, 0.04),
                "information_criterion": 3.0,
                "interpretable": True,
            },
            {
                "k": 5,
                "converged": True,
                "stability": 0.9,
                "weighted_shares": (0.3, 0.2, 0.2, 0.15, 0.15),
                "information_criterion": 4.0,
                "interpretable": True,
            },
            {
                "k": 6,
                "converged": True,
                "stability": 0.9,
                "weighted_shares": (0.2, 0.2, 0.2, 0.15, 0.15, 0.1),
                "information_criterion": 5.0,
                "interpretable": False,
            },
        ]

        self.assertEqual(select_candidate(diagnostics)["selected_k"], 5)
        diagnostics[-1]["information_criterion"] = 3.5
        with self.assertRaisesRegex(LCAError, "interpretability gate"):
            select_candidate(diagnostics)

    def test_disclosure_guard_requires_at_least_30_unweighted_records(self):
        self.assertTrue(disclosure_ready((30, 120)))
        self.assertFalse(disclosure_ready((29, 120)))
        with self.assertRaisesRegex(LCAError, "nonempty sequence"):
            disclosure_ready(())


if __name__ == "__main__":
    unittest.main()
