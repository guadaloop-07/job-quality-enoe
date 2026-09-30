#!/usr/bin/env python3
"""Fail closed when the approved ENOE profile-model contract is changed unsafely."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "config" / "profile_model_contract.json"
DEVELOPMENT_PERIODS = tuple(f"{year}Q{quarter}" for year in (2023, 2024) for quarter in range(1, 5))
SELECTION_PERIODS = tuple(f"2025Q{quarter}" for quarter in range(1, 5))
EVALUATION_PERIODS = ("2026Q1", "2026Q2")
REQUIRED_FEATURES = {
    "income_band",
    "working_time_duration",
    "employment_health_access",
    "non_health_benefits",
    "contract_status",
}
PROHIBITED_COLUMNS = {
    "analysis_weight",
    "c_ocu11c",
    "emp_ppal",
    "emple7c",
    "entity",
    "income_exact",
    "medica5c",
    "p3i",
    "pos_ocu",
    "rama",
    "survey_quarter",
    "survey_year",
    "tue_ppal",
    "weekly_hours",
}
SELECTION_ORDER = (
    "convergence",
    "temporal_stability",
    "minimum_weighted_share",
    "information_criterion",
    "interpretability",
)
LONGITUDINAL_SENSITIVITY_HIERARCHY = {
    "primary": "exclude_target_role_signatures_anchored_by_unambiguous_adjacent_n_ent_increment",
    "sensitivity_a": "complete_temporal_target_role_universe",
    "sensitivity_b": "exclude_all_candidate_signature_matches_with_any_prior_role",
    "model_selection": "primary_only",
    "sensitivity_role": "fixed_solution_robustness_only",
}
OUT_OF_SCOPE = {
    "individual_prediction",
    "individual_ranking",
    "causal_inference",
    "municipal_profiles",
    "2026_training",
    "public_deployment",
}


class ModelContractError(ValueError):
    """Raised when a model contract would permit unsupported fitting."""


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ModelContractError(f"{name} must be an object")
    return value


def _strings(value: object, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, str)
        or not all(isinstance(item, str) for item in value)
    ):
        raise ModelContractError(f"{name} must be a list of strings")
    return tuple(value)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, object]:
    """Load a JSON object without accepting malformed or non-object contracts."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelContractError(f"could not read model contract: {path}") from error
    if not isinstance(loaded, dict):
        raise ModelContractError("model contract must be a JSON object")
    return loaded


def validate_contract(contract: Mapping[str, object]) -> dict[str, object]:
    """Validate fixed scope, feature roles, temporal isolation, and fit guardrails."""
    if contract.get("schema_version") != "1.0":
        raise ModelContractError("unsupported model contract schema version")
    if (
        contract.get("fit_status") != "contract_only"
        or contract.get("model_artifacts_allowed") is not False
    ):
        raise ModelContractError("the model contract must not authorize fitting")

    task = _mapping(contract.get("task"), "task")
    if task.get("kind") != "descriptive_weighted_segmentation":
        raise ModelContractError("model task must remain descriptive weighted segmentation")
    if task.get("official_category_claim") != "prohibited":
        raise ModelContractError("model contract must prohibit official-category claims")

    source = _mapping(contract.get("source"), "source")
    if source.get("prepared_view") != "analysis.enoe_person_quarter_prepared":
        raise ModelContractError("model source must be the prepared person-quarter view")
    if (
        source.get("unit_of_analysis") != "person-quarter"
        or source.get("domain") != "Jalisco statewide only"
    ):
        raise ModelContractError("model contract must retain its approved unit and domain")

    features = contract.get("fit_features")
    if not isinstance(features, Sequence) or isinstance(features, str):
        raise ModelContractError("fit_features must be a list")
    names: set[str] = set()
    source_columns: set[str] = set()
    for feature in features:
        item = _mapping(feature, "fit feature")
        name = item.get("name")
        if not isinstance(name, str):
            raise ModelContractError("fit feature name must be a string")
        if item.get("encoding") != "categorical_response_state":
            raise ModelContractError(f"{name} must preserve categorical response states")
        columns = _strings(item.get("source_columns"), f"{name}.source_columns")
        states = _strings(item.get("response_states"), f"{name}.response_states")
        if not columns or not states:
            raise ModelContractError(f"{name} must declare source columns and response states")
        names.add(name)
        source_columns.update(columns)
    if len(names) != len(features) or names != REQUIRED_FEATURES:
        raise ModelContractError("fit features differ from the approved five dimensions")

    prohibited = set(_strings(contract.get("prohibited_fit_columns"), "prohibited_fit_columns"))
    if prohibited != PROHIBITED_COLUMNS:
        raise ModelContractError("prohibited fit columns differ from the approved contract")
    if source_columns & prohibited:
        raise ModelContractError("a prohibited field appears in fit features")

    descriptive = _mapping(contract.get("descriptive_only_fields"), "descriptive_only_fields")
    if not {
        "employment_formality",
        "informal_sector",
        "questionnaire_specific_contract_field",
    }.issubset(descriptive):
        raise ModelContractError("descriptive-only exclusions are incomplete")

    missingness = _mapping(contract.get("missingness"), "missingness")
    if (
        missingness.get("imputation") != "prohibited"
        or missingness.get("encoding") != "explicit_response_state"
    ):
        raise ModelContractError("model contract must prohibit substantive imputation")

    weighting = _mapping(contract.get("weighting"), "weighting")
    if (
        weighting.get("source_column") != "analysis_weight"
        or weighting.get("eligibility") != "analysis_weight > 0"
        or weighting.get("fit_normalization") != "sum_to_one_within_survey_quarter"
    ):
        raise ModelContractError(
            "model weighting differs from the approved quarter-normalized rule"
        )

    temporal = _mapping(contract.get("temporal_split"), "temporal_split")
    development = _strings(temporal.get("development_periods"), "development_periods")
    selection = _strings(temporal.get("selection_periods"), "selection_periods")
    evaluation = _strings(temporal.get("evaluation_periods"), "evaluation_periods")
    if (development, selection, evaluation) != (
        DEVELOPMENT_PERIODS,
        SELECTION_PERIODS,
        EVALUATION_PERIODS,
    ):
        raise ModelContractError("temporal periods differ from the approved split")
    if (
        temporal.get("evaluation_source") != "official_archives_not_staging"
        or temporal.get("evaluation_rule") != "not_in_training_or_selection"
    ):
        raise ModelContractError("2026 must remain a held-out archive-only evaluation")

    dependence = _mapping(contract.get("dependence_control"), "dependence_control")
    if dependence.get("non_temporal_resampling") != "prohibited_until_repeat_observation_audit":
        raise ModelContractError("non-temporal resampling must remain prohibited")
    if (
        dependence.get("selection_design") != "quarter_based_temporal_holdout"
        or dependence.get("evaluation_overlap_audit")
        != "required_before_interpreting_temporal_results"
    ):
        raise ModelContractError("repeat-observation safeguards are incomplete")
    hierarchy = _mapping(
        dependence.get("longitudinal_sensitivity_hierarchy"),
        "longitudinal_sensitivity_hierarchy",
    )
    if dict(hierarchy) != LONGITUDINAL_SENSITIVITY_HIERARCHY:
        raise ModelContractError(
            "longitudinal sensitivity hierarchy differs from the approved policy"
        )

    candidate = _mapping(contract.get("candidate_model"), "candidate_model")
    if candidate.get("family") != "weighted_latent_class_analysis":
        raise ModelContractError("candidate model family differs from the approved contract")
    if tuple(candidate.get("candidate_profile_counts", ())) != (2, 3, 4, 5, 6):
        raise ModelContractError("candidate profile counts differ from the approved range")
    if _strings(candidate.get("selection_order"), "selection_order") != SELECTION_ORDER:
        raise ModelContractError("candidate selection order differs from the approved gates")
    if candidate.get("minimum_weighted_share") != 0.05 or candidate.get("minimum_stability") != 0.8:
        raise ModelContractError(
            "candidate acceptance thresholds differ from the approved contract"
        )

    reproducibility = _mapping(contract.get("reproducibility"), "reproducibility")
    required_metadata = set(_strings(reproducibility.get("required_run_metadata"), "metadata"))
    if required_metadata != {
        "contract_sha256",
        "source_archive_sha256",
        "code_commit",
        "random_seed",
        "period_role",
    }:
        raise ModelContractError("reproducibility metadata is incomplete")
    if (
        reproducibility.get("microdata_in_git") != "prohibited"
        or reproducibility.get("model_binary_in_git") != "prohibited"
    ):
        raise ModelContractError("model contract must keep sensitive artifacts out of Git")

    disclosure = _mapping(contract.get("disclosure"), "disclosure")
    if disclosure.get("minimum_unweighted_records") != 30:
        raise ModelContractError(
            "model disclosure threshold differs from the published profile rule"
        )
    if set(_strings(contract.get("out_of_scope"), "out_of_scope")) != OUT_OF_SCOPE:
        raise ModelContractError("out-of-scope protections differ from the approved contract")
    return {
        "contract_validated": True,
        "fit_status": "contract_only",
        "fit_features": sorted(names),
        "development_periods": list(development),
        "selection_periods": list(selection),
        "evaluation_periods": list(evaluation),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()
    print(json.dumps(validate_contract(load_contract(args.contract)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
