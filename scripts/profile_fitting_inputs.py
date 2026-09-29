#!/usr/bin/env python3
"""Build guarded ENOE profile-fitting inputs without authorizing model fitting."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

if __package__:
    from scripts.enoe_ingest import database_sql
    from scripts.enoe_temporal_audit import (
        EVALUATION_PERIODS as ARCHIVE_EVALUATION_PERIODS,
    )
    from scripts.enoe_temporal_audit import (
        REFERENCE_PERIOD,
        audit_temporal_evaluation,
    )
    from scripts.profile_model_contract import (
        DEVELOPMENT_PERIODS,
        EVALUATION_PERIODS,
        SELECTION_PERIODS,
        load_contract,
        validate_contract,
    )
else:
    from enoe_ingest import database_sql
    from enoe_temporal_audit import (
        EVALUATION_PERIODS as ARCHIVE_EVALUATION_PERIODS,
    )
    from enoe_temporal_audit import (
        REFERENCE_PERIOD,
        audit_temporal_evaluation,
    )
    from profile_model_contract import (
        DEVELOPMENT_PERIODS,
        EVALUATION_PERIODS,
        SELECTION_PERIODS,
        load_contract,
        validate_contract,
    )

FIT_FEATURES = (
    "income_band",
    "working_time_duration",
    "employment_health_access",
    "non_health_benefits",
    "contract_status",
)
METADATA_COLUMNS = {"survey_year", "survey_quarter", "analysis_weight"}
FEATURE_SOURCE_COLUMNS = {
    "income_band",
    "income_band_state",
    "dur9c",
    "has_health_access",
    "health_access_state",
    "has_other_benefits",
    "other_benefits_state",
    "has_written_contract",
    "contract_type",
    "contract_type_state",
}
EXPECTED_INPUT_COLUMNS = METADATA_COLUMNS | FEATURE_SOURCE_COLUMNS
AUDIT_FIELDS = (
    "invalid_weight",
    "invalid_income_band",
    "invalid_working_time_duration",
    "invalid_employment_health_access",
    "invalid_non_health_benefits",
    "invalid_contract_status",
)


class FittingInputError(ValueError):
    """Raised when an input could permit an unsafe model fit."""


CORE_INPUT_AUDIT_SQL = """
WITH encoded AS (
    SELECT
        survey_year,
        survey_quarter,
        analysis_weight,
        CASE
            WHEN income_band_state = 'observed_band' AND income_band BETWEEN 1 AND 5
                THEN 'income_band_' || income_band::text
            WHEN income_band_state = 'no_income' AND income_band = 6 THEN 'no_income'
            WHEN income_band_state = 'unspecified' AND income_band IS NULL THEN 'unspecified'
            WHEN income_band_state = 'missing' AND income_band IS NULL THEN 'missing'
        END AS income_band_token,
        CASE
            WHEN dur9c = '1' THEN 'temporary_absence'
            WHEN dur9c IN ('2', '3', '4', '5', '6', '7', '8') THEN 'duration_' || dur9c
            WHEN dur9c = '9' THEN 'unspecified'
            WHEN dur9c IS NULL THEN 'missing'
        END AS working_time_duration_token,
        CASE
            WHEN health_access_state = 'observed' AND has_health_access IS TRUE THEN 'with_access'
            WHEN health_access_state = 'observed' AND has_health_access IS FALSE THEN 'without_access'
            WHEN health_access_state = 'unspecified' AND has_health_access IS NULL THEN 'unspecified'
            WHEN health_access_state = 'missing' AND has_health_access IS NULL THEN 'missing'
        END AS employment_health_access_token,
        CASE
            WHEN other_benefits_state = 'observed' AND has_other_benefits IS TRUE THEN 'with_benefits'
            WHEN other_benefits_state = 'observed' AND has_other_benefits IS FALSE THEN 'without_benefits'
            WHEN other_benefits_state = 'unspecified' AND has_other_benefits IS NULL THEN 'unspecified'
            WHEN other_benefits_state = 'missing' AND has_other_benefits IS NULL THEN 'missing'
        END AS non_health_benefits_token,
        CASE
            WHEN contract_type_state = 'observed_type'
                AND has_written_contract IS TRUE
                AND contract_type IN ('temporary', 'indefinite') THEN contract_type
            WHEN contract_type_state = 'type_unspecified'
                AND has_written_contract IS TRUE
                AND contract_type IS NULL THEN 'type_unspecified'
            WHEN contract_type_state = 'not_applicable'
                AND has_written_contract IS FALSE
                AND contract_type IS NULL THEN 'without_written_contract'
            WHEN contract_type_state = 'unspecified'
                AND has_written_contract IS NULL
                AND contract_type IS NULL THEN 'unspecified'
            WHEN contract_type_state = 'missing'
                AND has_written_contract IS NULL
                AND contract_type IS NULL THEN 'missing'
        END AS contract_status_token
    FROM analysis.enoe_person_quarter_prepared
), period_audit AS (
    SELECT
        survey_year,
        survey_quarter,
        count(*) AS records,
        coalesce(sum(analysis_weight), 0) AS positive_weight,
        count(*) FILTER (WHERE analysis_weight <= 0) AS invalid_weight,
        count(*) FILTER (WHERE income_band_token IS NULL) AS invalid_income_band,
        count(*) FILTER (WHERE working_time_duration_token IS NULL)
            AS invalid_working_time_duration,
        count(*) FILTER (WHERE employment_health_access_token IS NULL)
            AS invalid_employment_health_access,
        count(*) FILTER (WHERE non_health_benefits_token IS NULL)
            AS invalid_non_health_benefits,
        count(*) FILTER (WHERE contract_status_token IS NULL) AS invalid_contract_status
    FROM encoded
    GROUP BY survey_year, survey_quarter
)
SELECT coalesce(json_agg(json_build_object(
    'period', survey_year::text || 'Q' || survey_quarter::text,
    'records', records,
    'positive_weight', positive_weight,
    'invalid_weight', invalid_weight,
    'invalid_income_band', invalid_income_band,
    'invalid_working_time_duration', invalid_working_time_duration,
    'invalid_employment_health_access', invalid_employment_health_access,
    'invalid_non_health_benefits', invalid_non_health_benefits,
    'invalid_contract_status', invalid_contract_status
) ORDER BY survey_year, survey_quarter), '[]'::json)::text
FROM period_audit;
"""

REPEAT_OVERLAP_SQL = """
WITH role_records AS (
    SELECT
        CASE
            WHEN survey_year IN (2023, 2024) THEN 'development'
            WHEN survey_year = 2025 THEN 'selection'
        END AS role,
        entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
    FROM analysis.enoe_person_quarter_prepared
), signatures AS (
    SELECT DISTINCT role, entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
    FROM role_records
), development AS (
    SELECT entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
    FROM signatures WHERE role = 'development'
), selection AS (
    SELECT entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
    FROM signatures WHERE role = 'selection'
), overlap AS (
    SELECT entity, cd_a, con, v_sel, n_hog, h_mud, n_ren FROM development
    INTERSECT
    SELECT entity, cd_a, con, v_sel, n_hog, h_mud, n_ren FROM selection
)
SELECT json_build_object(
    'candidate_signature', 'entity_cd_a_con_v_sel_n_hog_h_mud_n_ren',
    'candidate_signature_is_approved_linkage', false,
    'development_distinct_signatures', (SELECT count(*) FROM development),
    'selection_distinct_signatures', (SELECT count(*) FROM selection),
    'cross_role_candidate_signature_overlap', (SELECT count(*) FROM overlap),
    'non_temporal_resampling', 'prohibited_until_repeat_observation_audit'
)::text;
"""


def _period_label(row: Mapping[str, object]) -> str:
    try:
        year = int(row["survey_year"])
        quarter = int(row["survey_quarter"])
    except (KeyError, TypeError, ValueError) as error:
        raise FittingInputError(
            "input row requires numeric survey_year and survey_quarter"
        ) from error
    return f"{year}Q{quarter}"


def period_role(period: str) -> str:
    if period in DEVELOPMENT_PERIODS:
        return "development"
    if period in SELECTION_PERIODS:
        return "selection"
    if period in EVALUATION_PERIODS:
        return "evaluation"
    raise FittingInputError(f"period is outside the model contract: {period}")


def _weight(value: object) -> Decimal:
    try:
        weight = Decimal(str(value))
    except (ArithmeticError, ValueError) as error:
        raise FittingInputError("analysis_weight must be numeric") from error
    if weight <= 0:
        raise FittingInputError("analysis_weight must be positive")
    return weight


def _token_income(row: Mapping[str, object]) -> str:
    state, value = row["income_band_state"], row["income_band"]
    if state == "observed_band" and value in {1, 2, 3, 4, 5}:
        return f"income_band_{value}"
    if state == "no_income" and value == 6:
        return "no_income"
    if state in {"unspecified", "missing"} and value is None:
        return str(state)
    raise FittingInputError("income band conflicts with its response state")


def _token_duration(row: Mapping[str, object]) -> str:
    value = row["dur9c"]
    if value is None:
        return "missing"
    code = str(value)
    if code == "1":
        return "temporary_absence"
    if code in {"2", "3", "4", "5", "6", "7", "8"}:
        return f"duration_{code}"
    if code == "9":
        return "unspecified"
    raise FittingInputError("working-time duration has an invalid code")


def _token_binary(value: object, state: object, positive: str, negative: str, name: str) -> str:
    if state == "observed" and value is True:
        return positive
    if state == "observed" and value is False:
        return negative
    if state in {"unspecified", "missing"} and value is None:
        return str(state)
    raise FittingInputError(f"{name} conflicts with its response state")


def _token_contract(row: Mapping[str, object]) -> str:
    written = row["has_written_contract"]
    contract_type = row["contract_type"]
    state = row["contract_type_state"]
    if (
        state == "observed_type"
        and written is True
        and contract_type in {"temporary", "indefinite"}
    ):
        return str(contract_type)
    if state == "type_unspecified" and written is True and contract_type is None:
        return "type_unspecified"
    if state == "not_applicable" and written is False and contract_type is None:
        return "without_written_contract"
    if state in {"unspecified", "missing"} and written is None and contract_type is None:
        return str(state)
    raise FittingInputError("contract status conflicts with its response state")


def encode_feature_row(row: Mapping[str, object]) -> dict[str, object]:
    """Encode the five contract-approved dimensions without accepting extra inputs."""
    if set(row) != EXPECTED_INPUT_COLUMNS:
        unexpected = sorted(set(row) - EXPECTED_INPUT_COLUMNS)
        missing = sorted(EXPECTED_INPUT_COLUMNS - set(row))
        raise FittingInputError(
            f"input columns differ from contract: extra={unexpected}, missing={missing}"
        )
    period = _period_label(row)
    return {
        "period": period,
        "period_role": period_role(period),
        "weight": _weight(row["analysis_weight"]),
        "tokens": {
            "income_band": _token_income(row),
            "working_time_duration": _token_duration(row),
            "employment_health_access": _token_binary(
                row["has_health_access"],
                row["health_access_state"],
                "with_access",
                "without_access",
                "employment health access",
            ),
            "non_health_benefits": _token_binary(
                row["has_other_benefits"],
                row["other_benefits_state"],
                "with_benefits",
                "without_benefits",
                "non-health benefits",
            ),
            "contract_status": _token_contract(row),
        },
    }


def audit_encoded_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return aggregate-only role evidence and normalize weights within each quarter."""
    encoded = [encode_feature_row(row) for row in rows]
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in encoded:
        grouped[str(row["period"])].append(row)
    expected = DEVELOPMENT_PERIODS + SELECTION_PERIODS
    if tuple(sorted(grouped)) != expected:
        raise FittingInputError("core fitting inputs have incomplete or unexpected periods")

    periods = []
    for period in expected:
        period_rows = grouped[period]
        total_weight = sum((row["weight"] for row in period_rows), Decimal())
        normalized_weight_sum = sum(
            (row["weight"] / total_weight for row in period_rows), Decimal()
        )
        categories: dict[str, dict[str, int]] = {
            feature: defaultdict(int) for feature in FIT_FEATURES
        }
        for row in period_rows:
            for feature, token in row["tokens"].items():
                categories[feature][str(token)] += 1
        periods.append(
            {
                "period": period,
                "period_role": period_role(period),
                "records": len(period_rows),
                "positive_weight": str(total_weight),
                "normalized_weight_sum": str(normalized_weight_sum),
                "feature_categories": {
                    feature: dict(sorted(values.items())) for feature, values in categories.items()
                },
            }
        )
    return {
        "fit_authorized": False,
        "fit_status": "contract_only",
        "input_grain": "one encoded person-quarter per local row",
        "periods": periods,
    }


def validate_core_audit(periods: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Reject incomplete, invalid, or nonpositive core inputs from aggregate evidence."""
    labels = tuple(str(period.get("period", "")) for period in periods)
    expected = DEVELOPMENT_PERIODS + SELECTION_PERIODS
    if labels != expected:
        raise FittingInputError("core fitting inputs have incomplete or unexpected periods")
    failures: list[str] = []
    for period in periods:
        label = str(period["period"])
        if Decimal(str(period.get("positive_weight", 0))) <= 0:
            failures.append(f"{label}: positive_weight is not positive")
        for field in AUDIT_FIELDS:
            if period.get(field) != 0:
                failures.append(f"{label}: {field}={period.get(field)!r}")
    if failures:
        raise FittingInputError("profile fitting inputs are unsafe: " + "; ".join(failures))
    return {
        "core_periods": list(expected),
        "fit_authorized": False,
        "input_features_validated": True,
    }


def validate_repeat_overlap(overlap: Mapping[str, object]) -> dict[str, object]:
    """Report candidate-key overlap without treating it as approved longitudinal linkage."""
    if overlap.get("candidate_signature_is_approved_linkage") is not False:
        raise FittingInputError(
            "repeat-observation signature must not be treated as approved linkage"
        )
    if overlap.get("non_temporal_resampling") != "prohibited_until_repeat_observation_audit":
        raise FittingInputError("non-temporal resampling must remain prohibited")
    for field in (
        "development_distinct_signatures",
        "selection_distinct_signatures",
        "cross_role_candidate_signature_overlap",
    ):
        if not isinstance(overlap.get(field), int) or int(overlap[field]) < 0:
            raise FittingInputError(f"repeat-observation audit has invalid {field}")
    return {
        **dict(overlap),
        "interpretation": "candidate signature overlap is diagnostic only; it is not person linkage",
    }


def core_input_audit() -> dict[str, object]:
    """Run only aggregate database checks; never write inputs or fit a model."""
    contract = validate_contract(load_contract())
    try:
        periods = json.loads(database_sql(CORE_INPUT_AUDIT_SQL))
        overlap = json.loads(database_sql(REPEAT_OVERLAP_SQL))
    except json.JSONDecodeError as error:
        raise FittingInputError("fitting-input audit did not return JSON") from error
    if not isinstance(periods, list) or not all(isinstance(period, dict) for period in periods):
        raise FittingInputError("fitting-input audit returned invalid period evidence")
    if not isinstance(overlap, dict):
        raise FittingInputError("repeat-observation audit returned invalid evidence")
    result = validate_core_audit(periods)
    result.update(
        {
            "contract": contract,
            "periods": periods,
            "repeat_observation_audit": validate_repeat_overlap(overlap),
        }
    )
    return result


def evaluation_input_audit(
    reference_path: Path, evaluation_paths: Mapping[object, Path]
) -> dict[str, object]:
    """Accept only the already-governed 2026 archives as held-out evaluation inputs."""
    validate_contract(load_contract())
    evidence = audit_temporal_evaluation(reference_path, dict(evaluation_paths))
    periods = evidence.get("evaluation_periods")
    if (
        evidence.get("decision") != "source_integrity_passed_for_separate_temporal_evaluation"
        or not isinstance(periods, list)
        or tuple(period.get("period") for period in periods) != EVALUATION_PERIODS
    ):
        raise FittingInputError("evaluation inputs must be the audited 2026 temporal archives")
    return {
        "fit_authorized": False,
        "input_role": "held_out_evaluation_only",
        "evaluation_source": "official_archives_not_staging",
        "reference_period": evidence["reference_period"],
        "evaluation_periods": [
            {
                "period": period["period"],
                "candidate_records": period["candidate_records"],
                "provenance": period["provenance"],
            }
            for period in periods
        ],
    }


def _evaluation_paths(data_dir: Path) -> dict[object, Path]:
    return {period: data_dir / period.archive_name for period in ARCHIVE_EVALUATION_PERIODS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-core")
    evaluation = commands.add_parser("audit-evaluation")
    evaluation.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    args = parser.parse_args()

    if args.command == "audit-core":
        result = core_input_audit()
    else:
        result = evaluation_input_audit(
            args.data_dir / REFERENCE_PERIOD.archive_name,
            _evaluation_paths(args.data_dir),
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
