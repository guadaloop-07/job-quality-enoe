#!/usr/bin/env python3
"""Validate and document the analytical ENOE preparation view with aggregate-only output."""

from __future__ import annotations

import json
from collections.abc import Sequence

if __package__:
    from scripts.enoe_ingest import database_sql
else:
    from enoe_ingest import database_sql

CORE_PERIODS = tuple(f"{year}Q{quarter}" for year in range(2023, 2026) for quarter in range(1, 5))


class PreparationError(ValueError):
    """Raised when official staging cannot safely support analytical preparation."""


PREPARATION_AUDIT_SQL = """
WITH period_audit AS (
    SELECT
        source.survey_year,
        source.survey_quarter,
        count(*) AS records,
        coalesce(sum(source.fac_tri), 0) AS positive_weight,
        array_agg(DISTINCT source.source_archive_sha256) AS source_archive_sha256s,
        count(*) FILTER (
            WHERE source.entity <> 14
               OR source.r_def <> '0'
               OR source.c_res NOT IN ('1', '3')
               OR source.eda !~ '^[0-9]+$'
               OR source.eda::integer NOT BETWEEN 15 AND 98
               OR source.clase2 <> '1'
               OR source.pos_ocu <> '1'
        ) AS invalid_universe,
        count(*) FILTER (
            WHERE source.ingocup IS NOT NULL
              AND CASE
                  WHEN source.ingocup ~ '^[0-9]+$' THEN source.ingocup::numeric
                  ELSE -1
              END NOT BETWEEN 0 AND 999998
        ) AS invalid_income_exact,
        count(*) FILTER (WHERE source.ing7c IS NOT NULL AND source.ing7c NOT IN ('1', '2', '3', '4', '5', '6', '7'))
            AS invalid_income_band,
        count(*) FILTER (
            WHERE source.hrsocup IS NOT NULL
              AND CASE
                  WHEN source.hrsocup ~ '^[0-9]+$' THEN source.hrsocup::numeric
                  ELSE -1
              END NOT BETWEEN 0 AND 168
        ) AS invalid_hours,
        count(*) FILTER (
            WHERE source.hrsocup = '0' AND coalesce(source.dur9c NOT IN ('1', '9'), true)
        ) AS invalid_zero_hour_reason,
        count(*) FILTER (WHERE source.tip_con IS NOT NULL AND source.tip_con NOT IN ('1', '2', '3', '4', '5', '6'))
            AS invalid_contract,
        count(*) FILTER (WHERE source.seg_soc IS NOT NULL AND source.seg_soc NOT IN ('1', '2', '3'))
            AS invalid_health_access,
        count(*) FILTER (WHERE source.pre_asa IS NOT NULL AND source.pre_asa NOT IN ('1', '2', '3'))
            AS invalid_other_benefits,
        count(*) FILTER (
            WHERE NOT EXISTS (
                SELECT 1
                FROM metadata.source_archives AS archive
                WHERE archive.source_name = 'INEGI ENOE 15 and over CSV'
                  AND archive.survey_year = source.survey_year
                  AND archive.survey_quarter = source.survey_quarter
                  AND archive.content_sha256 = source.source_archive_sha256
            )
        ) AS unmatched_source_provenance
    FROM staging.enoe_person_quarter AS source
    WHERE source.survey_year BETWEEN 2023 AND 2025
    GROUP BY source.survey_year, source.survey_quarter
)
SELECT coalesce(
    json_agg(
        json_build_object(
            'period', survey_year::text || 'Q' || survey_quarter::text,
            'records', records,
            'positive_weight', positive_weight,
            'source_archive_sha256s', source_archive_sha256s,
            'invalid_universe', invalid_universe,
            'invalid_income_exact', invalid_income_exact,
            'invalid_income_band', invalid_income_band,
            'invalid_hours', invalid_hours,
            'invalid_zero_hour_reason', invalid_zero_hour_reason,
            'invalid_contract', invalid_contract,
            'invalid_health_access', invalid_health_access,
            'invalid_other_benefits', invalid_other_benefits,
            'unmatched_source_provenance', unmatched_source_provenance
        )
        ORDER BY survey_year, survey_quarter
    ),
    '[]'::json
)::text
FROM period_audit;
"""

INVALID_FIELDS = (
    "invalid_universe",
    "invalid_income_exact",
    "invalid_income_band",
    "invalid_hours",
    "invalid_zero_hour_reason",
    "invalid_contract",
    "invalid_health_access",
    "invalid_other_benefits",
    "unmatched_source_provenance",
)


def audit_payload(periods: Sequence[dict[str, object]]) -> dict[str, object]:
    """Reject incomplete or invalid staging before exposing aggregate preparation evidence."""
    labels = tuple(str(period.get("period", "")) for period in periods)
    if labels != CORE_PERIODS:
        raise PreparationError("core window is incomplete or has unexpected periods")

    failures: list[str] = []
    for period in periods:
        label = str(period["period"])
        hashes = period.get("source_archive_sha256s")
        if not isinstance(hashes, list) or len(hashes) != 1:
            failures.append(f"{label}: source provenance is not unique")
        for field in INVALID_FIELDS:
            if period.get(field) != 0:
                failures.append(f"{label}: {field}={period.get(field)!r}")
    if failures:
        raise PreparationError("analytical preparation is unsafe: " + "; ".join(failures))

    return {
        "source": "repository-owned official ENOE staging",
        "unit_of_analysis": "person-quarter",
        "core_periods": list(CORE_PERIODS),
        "prepared_view": "analysis.enoe_person_quarter_prepared",
        "periods": list(periods),
        "reconciled": True,
    }


def preparation_audit() -> dict[str, object]:
    """Run the database audit and return aggregate-only, provenance-bearing evidence."""
    try:
        periods = json.loads(database_sql(PREPARATION_AUDIT_SQL))
    except json.JSONDecodeError as error:
        raise PreparationError("database preparation audit did not return JSON") from error
    if not isinstance(periods, list) or not all(isinstance(period, dict) for period in periods):
        raise PreparationError("database preparation audit returned an invalid structure")
    return audit_payload(periods)


def main() -> None:
    print(json.dumps(preparation_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
