#!/usr/bin/env python3
"""Fit guarded weighted categorical LCA in memory; ENOE fitting remains prohibited."""

from __future__ import annotations

import argparse
import itertools
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

if __package__:
    from scripts.profile_fitting_inputs import FIT_FEATURES
    from scripts.profile_model_contract import load_contract, validate_contract
else:
    from profile_fitting_inputs import FIT_FEATURES
    from profile_model_contract import load_contract, validate_contract


class LCAError(ValueError):
    """Raised when an LCA operation would violate the guarded protocol."""


@dataclass(frozen=True)
class LCAFit:
    k: int
    class_probabilities: np.ndarray
    conditional_probabilities: tuple[np.ndarray, ...]
    categories: tuple[tuple[str, ...], ...]
    log_likelihood: float
    converged: bool
    iterations: int


def _inputs(
    rows: Sequence[Mapping[str, object]],
) -> tuple[np.ndarray, np.ndarray, tuple[tuple[str, ...], ...]]:
    if not rows:
        raise LCAError("LCA requires at least one encoded row")
    tokens = []
    weights = []
    for row in rows:
        if set(row) != {"tokens", "weight"} or not isinstance(row.get("tokens"), Mapping):
            raise LCAError("LCA rows require only tokens and weight")
        values = row["tokens"]
        if set(values) != set(FIT_FEATURES) or not all(
            isinstance(value, str) for value in values.values()
        ):
            raise LCAError("LCA row tokens differ from the five approved dimensions")
        try:
            weight = float(row["weight"])
        except (TypeError, ValueError) as error:
            raise LCAError("LCA weight must be numeric") from error
        if not np.isfinite(weight) or weight <= 0:
            raise LCAError("LCA weight must be positive")
        tokens.append([str(values[feature]) for feature in FIT_FEATURES])
        weights.append(weight)
    categories = tuple(
        tuple(sorted({row[index] for row in tokens})) for index in range(len(FIT_FEATURES))
    )
    encoded = np.asarray(
        [[categories[index].index(value) for index, value in enumerate(row)] for row in tokens]
    )
    return encoded, np.asarray(weights), categories


def _logsumexp(values: np.ndarray) -> np.ndarray:
    maximum = values.max(axis=1, keepdims=True)
    return maximum + np.log(np.exp(values - maximum).sum(axis=1, keepdims=True))


def fit_weighted_lca(
    rows: Sequence[Mapping[str, object]],
    k: int,
    seed: int,
    *,
    max_iterations: int = 500,
    tolerance: float = 1e-8,
    floor: float = 1e-12,
) -> LCAFit:
    """Fit one weighted categorical LCA start entirely in memory."""
    encoded, weights, categories = _inputs(rows)
    if k not in range(2, 7) or k > len(encoded):
        raise LCAError("LCA class count must be 2--6 and no greater than input rows")
    rng = np.random.default_rng(seed)
    pi = rng.dirichlet(np.ones(k))
    theta = tuple(rng.dirichlet(np.ones(len(values)), size=k) for values in categories)
    previous = None
    for iteration in range(1, max_iterations + 1):
        log_probability = np.broadcast_to(np.log(pi), (len(encoded), k)).copy()
        for feature, probabilities in enumerate(theta):
            log_probability += np.log(np.maximum(probabilities[:, encoded[:, feature]].T, floor))
        normalizer = _logsumexp(log_probability)
        responsibilities = np.exp(log_probability - normalizer)
        log_likelihood = float((weights * normalizer[:, 0]).sum())
        weighted = responsibilities * weights[:, None]
        pi = np.maximum(weighted.sum(axis=0) / weights.sum(), floor)
        pi /= pi.sum()
        updated = []
        for feature, values in enumerate(categories):
            counts = np.full((k, len(values)), floor)
            for code in range(len(values)):
                counts[:, code] += weighted[encoded[:, feature] == code].sum(axis=0)
            updated.append(counts / counts.sum(axis=1, keepdims=True))
        theta = tuple(updated)
        if previous is not None and abs(log_likelihood - previous) <= tolerance * (
            1 + abs(previous)
        ):
            return LCAFit(k, pi, theta, categories, log_likelihood, True, iteration)
        previous = log_likelihood
    return LCAFit(k, pi, theta, categories, float(previous), False, max_iterations)


def fit_multistart(
    rows: Sequence[Mapping[str, object]], k: int, base_seed: int
) -> tuple[LCAFit, int]:
    """Run the contract-fixed 32 deterministic starts and keep the best converged fit."""
    fits = [fit_weighted_lca(rows, k, base_seed + start) for start in range(32)]
    converged = [fit for fit in fits if fit.converged]
    if not converged:
        raise LCAError("no LCA start converged")
    return max(converged, key=lambda fit: fit.log_likelihood), len(converged)


def aligned_stability(reference: LCAFit, comparison: LCAFit) -> float:
    """Return 1 minus minimum aligned mean feature total variation distance."""
    if reference.k != comparison.k or reference.categories != comparison.categories:
        raise LCAError("LCA fits require equal class counts and category definitions for alignment")
    best = float("inf")
    for permutation in itertools.permutations(range(reference.k)):
        distances = []
        for feature in range(len(FIT_FEATURES)):
            aligned = comparison.conditional_probabilities[feature][list(permutation)]
            distance = (
                0.5
                * np.abs(reference.conditional_probabilities[feature] - aligned).sum(axis=1).mean()
            )
            distances.append(distance)
        best = min(best, float(np.mean(distances)))
    return 1 - best


def select_candidate(diagnostics: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
    """Apply the contract's predeclared candidate gates, in their fixed order.

    This consumes aggregate candidate diagnostics only; it does not authorize a
    fit, retrieve ENOE inputs, or emit model artifacts.
    """
    normalized: list[dict[str, object]] = []
    for item in diagnostics:
        if not isinstance(item, Mapping):
            raise LCAError("candidate diagnostics must be objects")
        try:
            k = int(item["k"])
            converged = item["converged"]
            stability = float(item["stability"])
            shares = tuple(float(value) for value in item["weighted_shares"])
            criterion = float(item["information_criterion"])
            interpretable = item["interpretable"]
        except (KeyError, TypeError, ValueError) as error:
            raise LCAError("candidate diagnostics are incomplete") from error
        if (
            k not in range(2, 7)
            or not isinstance(converged, bool)
            or not np.isfinite(stability)
            or not shares
            or not all(np.isfinite(value) and value >= 0 for value in shares)
            or not np.isfinite(criterion)
            or not isinstance(interpretable, bool)
        ):
            raise LCAError("candidate diagnostics contain invalid values")
        normalized.append(
            {
                "k": k,
                "converged": converged,
                "stability": stability,
                "weighted_shares": shares,
                "information_criterion": criterion,
                "interpretable": interpretable,
            }
        )

    converged = [item for item in normalized if item["converged"]]
    if not converged:
        raise LCAError("no candidate passed the convergence gate")
    stable = [item for item in converged if item["stability"] >= 0.8]
    if not stable:
        raise LCAError("no candidate passed the temporal stability gate")
    substantive = [item for item in stable if min(item["weighted_shares"]) >= 0.05]
    if not substantive:
        raise LCAError("no candidate passed the minimum weighted-share gate")
    best_criterion = min(item["information_criterion"] for item in substantive)
    best = [item for item in substantive if item["information_criterion"] == best_criterion]
    if len(best) != 1:
        raise LCAError("information criterion is tied; no undeclared tie-breaker exists")
    selected = best[0]
    if not selected["interpretable"]:
        raise LCAError("information-criterion winner failed the interpretability gate")
    return {
        "selected_k": selected["k"],
        "selection_order": [
            "convergence",
            "temporal_stability",
            "minimum_weighted_share",
            "information_criterion",
            "interpretability",
        ],
        "fit_authorized": False,
    }


def disclosure_ready(unweighted_profile_counts: Sequence[int]) -> bool:
    """Return whether every prospective published profile clears the 30-record rule."""
    if not unweighted_profile_counts or any(
        isinstance(count, bool) or not isinstance(count, int) for count in unweighted_profile_counts
    ):
        raise LCAError("disclosure counts must be a nonempty sequence of integers")
    if any(count < 0 for count in unweighted_profile_counts):
        raise LCAError("disclosure counts must be nonnegative")
    return all(count >= 30 for count in unweighted_profile_counts)


def synthetic_rows() -> list[dict[str, object]]:
    """Return deterministic, non-ENOE inputs with two separable latent patterns."""
    rows = []
    for group, count in (("secure", 90), ("precarious", 60)):
        for _ in range(count):
            rows.append(
                {
                    "weight": 2 if group == "secure" else 1,
                    "tokens": {
                        "income_band": ("income_band_5" if group == "secure" else "income_band_1"),
                        "working_time_duration": (
                            "duration_6" if group == "secure" else "duration_2"
                        ),
                        "employment_health_access": (
                            "with_access" if group == "secure" else "without_access"
                        ),
                        "non_health_benefits": (
                            "with_benefits" if group == "secure" else "without_benefits"
                        ),
                        "contract_status": (
                            "indefinite" if group == "secure" else "without_written_contract"
                        ),
                    },
                }
            )
    return rows


def synthetic_check() -> dict[str, object]:
    validate_contract(load_contract())
    fit, converged_starts = fit_multistart(synthetic_rows(), 2, 20260930)
    return {
        "fit_authorized": False,
        "input": "synthetic_only",
        "k": fit.k,
        "converged_starts": converged_starts,
        "iterations": fit.iterations,
        "self_aligned_stability": aligned_stability(fit, fit),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("synthetic-check",))
    parser.parse_args()
    print(json.dumps(synthetic_check(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
