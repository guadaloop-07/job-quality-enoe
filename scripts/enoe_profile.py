#!/usr/bin/env python3
"""Publish aggregate-only weighted ENOE classifier profiles by survey quarter."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

if __package__:
    from scripts.enoe_ingest import database_sql
else:
    from enoe_ingest import database_sql

CORE_PERIODS = tuple(f"{year}Q{quarter}" for year in range(2023, 2026) for quarter in range(1, 5))
MINIMUM_UNWEIGHTED_RECORDS = 30
SHARE_DECIMAL_TOLERANCE = Decimal("1e-12")
VALID_STATES = {"valid", "unspecified", "not_applicable", "missing"}
AUDIT_FIELDS = (
    "invalid_weight",
    "invalid_activity_branch",
    "invalid_occupation_group",
    "invalid_unit_size",
    "invalid_employment_formality",
    "invalid_informal_sector",
)


class ProfileError(ValueError):
    """Raised when profile inputs or aggregate outputs cannot be safely published."""


PROFILE_AUDIT_SQL = """
WITH period_audit AS (
    SELECT
        survey_year,
        survey_quarter,
        count(*) AS records,
        coalesce(sum(analysis_weight), 0) AS positive_weight,
        count(*) FILTER (WHERE analysis_weight <= 0) AS invalid_weight,
        count(*) FILTER (WHERE rama IS NOT NULL AND rama NOT IN ('1','2','3','4','5','6','7'))
            AS invalid_activity_branch,
        count(*) FILTER (
            WHERE c_ocu11c IS NOT NULL AND c_ocu11c NOT IN ('1','2','3','4','5','6','7','8','9','10','11')
        ) AS invalid_occupation_group,
        count(*) FILTER (WHERE emple7c IS NOT NULL AND emple7c NOT IN ('1','2','3','4','5','6','7'))
            AS invalid_unit_size,
        count(*) FILTER (WHERE emp_ppal IS NOT NULL AND emp_ppal NOT IN ('1','2'))
            AS invalid_employment_formality,
        count(*) FILTER (WHERE tue_ppal IS NOT NULL AND tue_ppal NOT IN ('1','2'))
            AS invalid_informal_sector
    FROM analysis.enoe_person_quarter_prepared
    GROUP BY survey_year, survey_quarter
)
SELECT coalesce(json_agg(json_build_object(
    'period', survey_year::text || 'Q' || survey_quarter::text,
    'records', records,
    'positive_weight', positive_weight,
    'invalid_weight', invalid_weight,
    'invalid_activity_branch', invalid_activity_branch,
    'invalid_occupation_group', invalid_occupation_group,
    'invalid_unit_size', invalid_unit_size,
    'invalid_employment_formality', invalid_employment_formality,
    'invalid_informal_sector', invalid_informal_sector
) ORDER BY survey_year, survey_quarter), '[]'::json)::text
FROM period_audit;
"""

PROFILE_SQL = """
SELECT coalesce(json_agg(json_build_object(
    'period', survey_year::text || 'Q' || survey_quarter::text,
    'classifier', classifier,
    'category_code', category_code,
    'category_state', category_state,
    'unweighted_records', unweighted_records,
    'weighted_records', weighted_records,
    'denominator_unweighted_records', denominator_unweighted_records,
    'denominator_weight', denominator_weight,
    'weighted_share', weighted_share
) ORDER BY survey_year, survey_quarter, classifier, category_code), '[]'::json)::text
FROM analysis.enoe_weighted_profile;
"""


def audit_payload(periods: Sequence[dict[str, object]]) -> dict[str, object]:
    """Require complete quarterly, positive-weight, classifier-valid profile inputs."""
    labels = tuple(str(period.get("period", "")) for period in periods)
    if labels != CORE_PERIODS:
        raise ProfileError("core window is incomplete or has unexpected periods")

    failures: list[str] = []
    for period in periods:
        label = str(period["period"])
        if Decimal(str(period.get("positive_weight", 0))) <= 0:
            failures.append(f"{label}: positive_weight is not positive")
        for field in AUDIT_FIELDS:
            if period.get(field) != 0:
                failures.append(f"{label}: {field}={period.get(field)!r}")
    if failures:
        raise ProfileError("weighted profile is unsafe: " + "; ".join(failures))
    return {"core_periods": list(CORE_PERIODS), "profile_inputs_validated": True}


def _decimal(row: dict[str, object], field: str) -> Decimal:
    try:
        return Decimal(str(row[field]))
    except (KeyError, ArithmeticError) as error:
        raise ProfileError(f"profile row has invalid {field}") from error


def _shares_match_weighted_records(cells: Sequence[dict[str, object]]) -> bool:
    """Accept only bounded database-division rounding in weighted shares."""
    denominator_weight = _decimal(cells[0], "denominator_weight")
    return all(
        abs(
            _decimal(cell, "weighted_share")
            - _decimal(cell, "weighted_records") / denominator_weight
        )
        <= SHARE_DECIMAL_TOLERANCE
        for cell in cells
    )


def report_payload(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    """Verify aggregate denominators and apply disclosure suppression before publication."""
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    identifiers: set[tuple[str, str, str, str]] = set()
    for row in rows:
        required = {
            "period",
            "classifier",
            "category_code",
            "category_state",
            "unweighted_records",
            "weighted_records",
            "denominator_unweighted_records",
            "denominator_weight",
            "weighted_share",
        }
        if not required.issubset(row):
            raise ProfileError("profile row has an invalid structure")
        state = str(row["category_state"])
        if state not in VALID_STATES:
            raise ProfileError(f"profile row has unsupported category state: {state}")
        identifier = (
            str(row["period"]),
            str(row["classifier"]),
            str(row["category_code"]),
            state,
        )
        if identifier in identifiers:
            raise ProfileError("profile output has duplicate categories")
        identifiers.add(identifier)
        grouped[identifier[:2]].append(row)

    published: list[dict[str, object]] = []
    for (period, classifier), cells in sorted(grouped.items()):
        denominator_records = _decimal(cells[0], "denominator_unweighted_records")
        denominator_weight = _decimal(cells[0], "denominator_weight")
        if denominator_records <= 0 or denominator_weight <= 0:
            raise ProfileError("profile output has a nonpositive denominator")
        if any(
            _decimal(cell, "denominator_unweighted_records") != denominator_records
            or _decimal(cell, "denominator_weight") != denominator_weight
            for cell in cells
        ):
            raise ProfileError("profile output has inconsistent denominators")
        if sum(_decimal(cell, "unweighted_records") for cell in cells) != denominator_records:
            raise ProfileError("profile output does not preserve the unweighted denominator")
        if sum(_decimal(cell, "weighted_records") for cell in cells) != denominator_weight:
            raise ProfileError("profile output does not preserve the weighted denominator")
        if not _shares_match_weighted_records(cells):
            raise ProfileError("profile output shares do not match weighted records")
        if abs(sum(_decimal(cell, "weighted_share") for cell in cells) - Decimal("1")) > (
            SHARE_DECIMAL_TOLERANCE * len(cells)
        ):
            raise ProfileError("profile output shares do not sum to one within decimal tolerance")
        for cell in cells:
            result = {
                "period": period,
                "classifier": classifier,
                "category_code": str(cell["category_code"]),
                "category_state": str(cell["category_state"]),
            }
            if _decimal(cell, "unweighted_records") < MINIMUM_UNWEIGHTED_RECORDS:
                result["suppressed"] = True
            else:
                result.update(
                    {
                        "suppressed": False,
                        "unweighted_records": str(cell["unweighted_records"]),
                        "weighted_records": str(cell["weighted_records"]),
                        "denominator_unweighted_records": str(
                            cell["denominator_unweighted_records"]
                        ),
                        "denominator_weight": str(cell["denominator_weight"]),
                        "weighted_share": str(cell["weighted_share"]),
                    }
                )
            published.append(result)
    return {
        "source": "repository-owned official ENOE staging",
        "unit_of_analysis": "person-quarter",
        "domain": "Jalisco statewide only; municipalities are not supported domains",
        "weight_rule": "analysis_weight > 0; FAC_TRI is used within each survey quarter",
        "disclosure": {
            "minimum_unweighted_records": MINIMUM_UNWEIGHTED_RECORDS,
            "rule": "Cells below the threshold retain only category state and suppression status.",
        },
        "estimates": published,
    }


def profile_report() -> dict[str, object]:
    """Query validated aggregate profile cells and return disclosure-controlled evidence only."""
    try:
        audited = json.loads(database_sql(PROFILE_AUDIT_SQL), parse_float=Decimal)
        rows = json.loads(database_sql(PROFILE_SQL), parse_float=Decimal)
    except json.JSONDecodeError as error:
        raise ProfileError("weighted profile database output did not return JSON") from error
    if not isinstance(audited, list) or not all(isinstance(period, dict) for period in audited):
        raise ProfileError("weighted profile audit returned an invalid structure")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ProfileError("weighted profile returned an invalid structure")
    result = audit_payload(audited)
    result.update(report_payload(rows))
    return result


def main() -> None:
    print(json.dumps(profile_report(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
