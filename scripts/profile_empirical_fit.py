#!/usr/bin/env python3
"""Run the authorized ENOE LCA candidate dossier without persisting microdata."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

if __package__:
    from scripts.enoe_ingest import database_sql
    from scripts.profile_fitting_inputs import (
        DEVELOPMENT_PERIODS,
        SELECTION_PERIODS,
        core_input_audit,
        encode_feature_row,
    )
    from scripts.profile_lca import LCAError, aligned_stability, fit_multistart
    from scripts.profile_longitudinal_sensitivities import audit_official_archives
    from scripts.profile_model_contract import load_contract, validate_contract
else:
    from enoe_ingest import database_sql
    from profile_fitting_inputs import (
        DEVELOPMENT_PERIODS,
        SELECTION_PERIODS,
        core_input_audit,
        encode_feature_row,
    )
    from profile_lca import LCAError, aligned_stability, fit_multistart
    from profile_longitudinal_sensitivities import audit_official_archives
    from profile_model_contract import load_contract, validate_contract


class EmpiricalFitError(ValueError):
    """Raised when a candidate dossier cannot honor the approved fit protocol."""


MODES = ("primary", "sensitivity_a", "sensitivity_b")
ARCHIVE_HASHES_SQL = """
SELECT coalesce(json_object_agg(
    survey_year::text || 'Q' || survey_quarter::text,
    content_sha256
), '{}'::json)::text
FROM metadata.source_archives
WHERE source_name = 'INEGI ENOE 15 and over CSV'
  AND (survey_year, survey_quarter) IN (
    (2023, 1), (2023, 2), (2023, 3), (2023, 4),
    (2024, 1), (2024, 2), (2024, 3), (2024, 4),
    (2025, 1), (2025, 2), (2025, 3), (2025, 4)
);
"""


def _input_sql(mode: str, role: str) -> str:
    if mode not in MODES or role not in {"development", "selection"}:
        raise EmpiricalFitError("fit input requires an approved mode and temporal role")
    periods = "(2023, 2024)" if role == "development" else "(2025)"
    primary_filter = """
        NOT (
            source.survey_year = 2025
            AND source.survey_quarter = 1
            AND EXISTS (
                SELECT 1 FROM anchored_selection AS anchor
                WHERE (anchor.entity, anchor.cd_a, anchor.con, anchor.v_sel, anchor.n_hog,
                    anchor.h_mud, anchor.n_ren)
                    = (source.entity, source.cd_a, source.con, source.v_sel, source.n_hog,
                        source.h_mud, source.n_ren)
            )
        )
    """
    conservative_filter = """
        NOT EXISTS (
            SELECT 1 FROM development_signatures AS prior
            WHERE (prior.entity, prior.cd_a, prior.con, prior.v_sel, prior.n_hog,
                prior.h_mud, prior.n_ren)
                = (source.entity, source.cd_a, source.con, source.v_sel, source.n_hog,
                    source.h_mud, source.n_ren)
        )
    """
    exclusion = "true"
    if role == "selection" and mode == "primary":
        exclusion = primary_filter
    if role == "selection" and mode == "sensitivity_b":
        exclusion = conservative_filter
    return f"""
WITH development_signatures AS (
    SELECT DISTINCT entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
    FROM analysis.enoe_person_quarter_prepared
    WHERE survey_year IN (2023, 2024)
), anchored_selection AS (
    SELECT DISTINCT following.entity, following.cd_a, following.con, following.v_sel,
        following.n_hog, following.h_mud, following.n_ren
    FROM analysis.enoe_person_quarter_prepared AS previous
    JOIN analysis.enoe_person_quarter_prepared AS following
        ON (previous.entity, previous.cd_a, previous.con, previous.v_sel, previous.n_hog,
            previous.h_mud, previous.n_ren)
            = (following.entity, following.cd_a, following.con, following.v_sel,
                following.n_hog, following.h_mud, following.n_ren)
    WHERE previous.survey_year = 2024 AND previous.survey_quarter = 4
      AND following.survey_year = 2025 AND following.survey_quarter = 1
      AND previous.n_ent ~ '^[1-5]$' AND following.n_ent ~ '^[1-5]$'
      AND following.n_ent::integer = previous.n_ent::integer + 1
), input_rows AS (
    SELECT source.survey_year, source.survey_quarter, source.analysis_weight,
        source.income_band, source.income_band_state, source.dur9c,
        source.has_health_access, source.health_access_state,
        source.has_other_benefits, source.other_benefits_state,
        source.has_written_contract, source.contract_type, source.contract_type_state
    FROM analysis.enoe_person_quarter_prepared AS source
    WHERE source.survey_year IN {periods} AND ({exclusion})
)
SELECT coalesce(json_agg(json_build_object(
    'survey_year', survey_year,
    'survey_quarter', survey_quarter,
    'analysis_weight', analysis_weight,
    'income_band', income_band,
    'income_band_state', income_band_state,
    'dur9c', dur9c,
    'has_health_access', has_health_access,
    'health_access_state', health_access_state,
    'has_other_benefits', has_other_benefits,
    'other_benefits_state', other_benefits_state,
    'has_written_contract', has_written_contract,
    'contract_type', contract_type,
    'contract_type_state', contract_type_state
) ORDER BY survey_year, survey_quarter), '[]'::json)::text
FROM input_rows;
"""


def _authorized_contract() -> dict[str, object]:
    contract = validate_contract(load_contract())
    if contract.get("fit_status") != "authorized_guarded_empirical_fit":
        raise EmpiricalFitError("model contract does not authorize the guarded empirical fit")
    return contract


def _normalized_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    encoded = [encode_feature_row(row) for row in rows]
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in encoded:
        grouped[str(row["period"])].append(row)
    expected = DEVELOPMENT_PERIODS + SELECTION_PERIODS
    if tuple(sorted(grouped)) != expected:
        raise EmpiricalFitError("empirical fit input has incomplete or unexpected periods")
    normalized: dict[str, list[dict[str, object]]] = {}
    for period in expected:
        period_rows = grouped[period]
        total = sum((Decimal(str(row["weight"])) for row in period_rows), Decimal())
        if total <= 0:
            raise EmpiricalFitError(f"{period}: normalized input has no positive weight")
        normalized[period] = [
            {
                "tokens": dict(row["tokens"]),
                "weight": float(Decimal(str(row["weight"])) / total),
            }
            for row in period_rows
        ]
    return normalized


def read_fit_inputs(mode: str) -> dict[str, list[dict[str, object]]]:
    """Read only approved fields in memory; SQL never returns candidate signatures."""
    _authorized_contract()
    records: list[Mapping[str, object]] = []
    for role in ("development", "selection"):
        try:
            result = json.loads(database_sql(_input_sql(mode, role)))
        except json.JSONDecodeError as error:
            raise EmpiricalFitError("fit input query did not return JSON") from error
        if not isinstance(result, list) or not all(isinstance(row, dict) for row in result):
            raise EmpiricalFitError("fit input query returned invalid rows")
        records.extend(result)
    return _normalized_rows(records)


def _preflight(data_dir: Path) -> dict[str, object]:
    core = core_input_audit()
    longitudinal = audit_official_archives(data_dir)
    if longitudinal.get("evaluation_archive_integrity_decision") != (
        "source_integrity_passed_for_separate_temporal_evaluation"
    ):
        raise EmpiricalFitError("held-out 2026 archive preflight did not pass")
    return {
        "core_inputs": {
            "input_features_validated": core["input_features_validated"],
            "core_periods": core["core_periods"],
        },
        "longitudinal_sensitivity": {
            "primary_boundary_anchor_counts": longitudinal["primary_boundary_anchor_counts"],
            "evaluation_archive_integrity_decision": longitudinal[
                "evaluation_archive_integrity_decision"
            ],
        },
    }


def _archive_hashes() -> dict[str, str]:
    try:
        hashes = json.loads(database_sql(ARCHIVE_HASHES_SQL))
    except json.JSONDecodeError as error:
        raise EmpiricalFitError("source archive query did not return JSON") from error
    expected = set(DEVELOPMENT_PERIODS + SELECTION_PERIODS)
    if (
        not isinstance(hashes, dict)
        or set(hashes) != expected
        or not all(isinstance(value, str) and len(value) == 64 for value in hashes.values())
    ):
        raise EmpiricalFitError("source archive hashes are incomplete")
    return dict(sorted(hashes.items()))


def _parameter_count(fit_categories: Sequence[Sequence[str]], k: int) -> int:
    return (k - 1) + k * sum(len(categories) - 1 for categories in fit_categories)


def _kish_effective_n(rows: Sequence[Mapping[str, object]]) -> float:
    total = sum(float(row["weight"]) for row in rows)
    squared = sum(float(row["weight"]) ** 2 for row in rows)
    if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-9) or squared <= 0:
        raise EmpiricalFitError("candidate rows must be normalized within quarter")
    return 1 / squared


def _pseudo_bic(log_likelihood: float, parameter_count: int, effective_n: float) -> float:
    return -2 * effective_n * log_likelihood + parameter_count * math.log(effective_n)


def _interpretability_evidence(fit) -> list[dict[str, object]]:
    """Return aggregate conditional distributions for documented human review."""
    profiles = []
    for profile_index, share in enumerate(fit.class_probabilities):
        dimensions = {}
        for feature, categories in zip(
            (
                "income_band",
                "working_time_duration",
                "employment_health_access",
                "non_health_benefits",
                "contract_status",
            ),
            fit.categories,
            strict=True,
        ):
            probabilities = fit.conditional_probabilities[len(dimensions)][profile_index]
            dimensions[feature] = dict(zip(categories, probabilities.tolist(), strict=True))
        profiles.append(
            {
                "profile_index": profile_index + 1,
                "weighted_share": float(share),
                "conditional_response_probabilities": dimensions,
            }
        )
    return profiles


def _candidate_summary(
    normalized: Mapping[str, Sequence[Mapping[str, object]]], k: int, base_seed: int
) -> dict[str, object]:
    development = [row for period in DEVELOPMENT_PERIODS for row in normalized[period]]
    try:
        reference, reference_converged = fit_multistart(development, k, base_seed + k * 100)
        quarterly = [
            (
                period,
                *fit_multistart(normalized[period], k, base_seed + k * 1000 + index),
            )
            for index, period in enumerate(SELECTION_PERIODS)
        ]
    except LCAError as error:
        return {"k": k, "converged": False, "failure": str(error)}
    stability = {period: aligned_stability(reference, fit) for period, fit, _ in quarterly}
    minimum_share = min(
        *reference.class_probabilities.tolist(),
        *(min(fit.class_probabilities.tolist()) for _, fit, _ in quarterly),
    )
    bic = sum(
        _pseudo_bic(
            fit.log_likelihood,
            _parameter_count(fit.categories, k),
            _kish_effective_n(normalized[period]),
        )
        for period, fit, _ in quarterly
    )
    return {
        "k": k,
        "converged": True,
        "development_converged_starts": reference_converged,
        "selection_converged_starts": {period: converged for period, _, converged in quarterly},
        "minimum_temporal_stability": min(stability.values()),
        "selection_temporal_stability": stability,
        "minimum_weighted_share": minimum_share,
        "selection_pseudo_bic": bic,
        "interpretability": "requires_documented_human_review",
        "development_profile_evidence": _interpretability_evidence(reference),
    }


def candidate_dossier(
    normalized: Mapping[str, Sequence[Mapping[str, object]]], base_seed: int
) -> dict[str, object]:
    """Fit primary candidates and return aggregate gates without model parameters."""
    expected = DEVELOPMENT_PERIODS + SELECTION_PERIODS
    if tuple(sorted(normalized)) != expected:
        raise EmpiricalFitError("candidate dossier requires every development and selection period")
    candidates = [_candidate_summary(normalized, k, base_seed) for k in range(2, 7)]
    survivors = [
        item
        for item in candidates
        if item.get("converged")
        and float(item["minimum_temporal_stability"]) >= 0.8
        and float(item["minimum_weighted_share"]) >= 0.05
    ]
    winner = None
    if survivors:
        winner = min(survivors, key=lambda item: float(item["selection_pseudo_bic"]))["k"]
    return {
        "fit_authorized": True,
        "input": "ephemeral_encoded_person_quarter_rows",
        "model_artifact_persisted": False,
        "selection_analysis": "primary_only",
        "information_criterion": "kish_rescaled_survey_pseudo_bic",
        "temporal_stability": "minimum_development_to_each_selection_quarter_alignment",
        "candidates": candidates,
        "information_criterion_winner_pending_interpretability": winner,
        "selection_status": (
            "awaiting_documented_interpretability_review"
            if winner is not None
            else "no_candidate_passed_pre_interpretability_gates"
        ),
    }


def _review(path: Path) -> dict[str, object]:
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EmpiricalFitError("interpretability review could not be read") from error
    if not isinstance(review, dict):
        raise EmpiricalFitError("interpretability review must be an object")
    dimensions = review.get("substantive_dimensions")
    if (
        not isinstance(review.get("selected_k"), int)
        or review["selected_k"] not in range(2, 7)
        or not isinstance(review.get("plain_language_label"), str)
        or not review["plain_language_label"].strip()
        or not isinstance(dimensions, list)
        or len(set(dimensions)) < 2
        or not set(dimensions).issubset(
            {
                "income_band",
                "working_time_duration",
                "employment_health_access",
                "non_health_benefits",
                "contract_status",
            }
        )
        or review.get("not_defined_by_response_states_alone") is not True
    ):
        raise EmpiricalFitError("interpretability review does not satisfy the approved rubric")
    return dict(review)


def fixed_solution_robustness(
    analyses: Mapping[str, Mapping[str, Sequence[Mapping[str, object]]]],
    review: Mapping[str, object],
    base_seed: int,
) -> dict[str, object]:
    """Evaluate a reviewed K only; sensitivity analyses can never select K."""
    if set(analyses) != set(MODES):
        raise EmpiricalFitError("fixed-solution robustness requires every approved analysis")
    k = int(review["selected_k"])
    expected = DEVELOPMENT_PERIODS + SELECTION_PERIODS
    if any(tuple(sorted(rows)) != expected for rows in analyses.values()):
        raise EmpiricalFitError("fixed-solution robustness has incomplete temporal inputs")
    primary = analyses["primary"]
    complete = {
        period: [
            row
            for row in primary[period]
            if not (set(row["tokens"].values()) & {"missing", "unspecified", "type_unspecified"})
        ]
        for period in expected
    }
    if any(not rows for rows in complete.values()):
        raise EmpiricalFitError("complete-response robustness has an empty quarter")
    return {
        "fit_authorized": True,
        "selection_analysis": "primary_only_already_reviewed",
        "selected_k": k,
        "interpretability_review": dict(review),
        "robustness_only": {
            mode: _candidate_summary(rows, k, base_seed + index * 10_000)
            for index, (mode, rows) in enumerate(analyses.items())
        }
        | {"complete_response_primary": _candidate_summary(complete, k, base_seed + 90_000)},
    }


def run_candidate_dossier(base_seed: int, data_dir: Path) -> dict[str, object]:
    """Execute the primary-only dossier and include reproducibility metadata."""
    _authorized_contract()
    preflight = _preflight(data_dir)
    normalized = read_fit_inputs("primary")
    contract_path = Path(__file__).resolve().parents[1] / "config" / "profile_model_contract.json"
    contract_hash = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
    ).stdout.strip()
    return {
        "run_metadata": {
            "contract_sha256": contract_hash,
            "source_archive_sha256": _archive_hashes(),
            "code_commit": commit,
            "random_seed": base_seed,
            "period_role": "development_and_primary_selection",
        },
        "preflight": preflight,
        "candidate_dossier": candidate_dossier(normalized, base_seed),
    }


def run_fixed_solution_robustness(
    review_path: Path, base_seed: int, data_dir: Path
) -> dict[str, object]:
    """Run only predeclared fixed-K robustness analyses after human review."""
    _authorized_contract()
    review = _review(review_path)
    preflight = _preflight(data_dir)
    return {
        "run_metadata": {
            "contract_sha256": hashlib.sha256(
                (
                    Path(__file__).resolve().parents[1] / "config" / "profile_model_contract.json"
                ).read_bytes()
            ).hexdigest(),
            "source_archive_sha256": _archive_hashes(),
            "code_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
            ).stdout.strip(),
            "random_seed": base_seed,
            "period_role": "fixed_solution_robustness",
        },
        "preflight": preflight,
        "fixed_solution_robustness": fixed_solution_robustness(
            {mode: read_fit_inputs(mode) for mode in MODES}, review, base_seed
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("candidate-dossier", "fixed-solution-robustness"))
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    parser.add_argument("--interpretability-review", type=Path)
    args = parser.parse_args()
    if args.command == "candidate-dossier":
        result = run_candidate_dossier(args.seed, args.data_dir)
    else:
        if args.interpretability_review is None:
            parser.error("fixed-solution-robustness requires --interpretability-review")
        result = run_fixed_solution_robustness(
            args.interpretability_review, args.seed, args.data_dir
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
