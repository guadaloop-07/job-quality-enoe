#!/usr/bin/env python3
"""Audit aggregate ENOE follow-up candidates without asserting person linkage."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

if __package__:
    from scripts.enoe_ingest import Period, database_sql, validate_archive
    from scripts.enoe_temporal_audit import (
        EVALUATION_PERIODS,
        REFERENCE_PERIOD,
        audit_temporal_evaluation,
    )
else:
    from enoe_ingest import Period, database_sql, validate_archive
    from enoe_temporal_audit import (
        EVALUATION_PERIODS,
        REFERENCE_PERIOD,
        audit_temporal_evaluation,
    )

CORE_PERIODS = tuple(f"{year}Q{quarter}" for year in range(2023, 2026) for quarter in range(1, 5))
EVALUATION_AUDIT_PERIODS = ("2025Q4", "2026Q1", "2026Q2")
FOLLOWUP_SIGNATURE_FIELDS = ("entity", "cd_a", "con", "v_sel", "n_hog", "h_mud", "n_ren")


class LongitudinalAuditError(ValueError):
    """Raised when aggregate follow-up evidence is structurally unsafe."""


CORE_AUDIT_SQL = """
WITH expected_periods AS (
    SELECT
        extract(year FROM period_start)::integer AS survey_year,
        extract(quarter FROM period_start)::integer AS survey_quarter,
        to_char(period_start, 'YYYY') || 'Q' || extract(quarter FROM period_start)::text AS period
    FROM generate_series(date '2023-01-01', date '2025-10-01', interval '3 months')
        AS periods(period_start)
), records AS (
    SELECT
        survey_year, survey_quarter, entity, cd_a, con, v_sel, n_hog, h_mud, n_ren,
        n_ent,
        CASE WHEN n_ent ~ '^[1-5]$' THEN n_ent::integer END AS visit_number
    FROM staging.enoe_person_quarter
    WHERE survey_year BETWEEN 2023 AND 2025
), signatures AS (
    SELECT
        survey_year, survey_quarter, entity, cd_a, con, v_sel, n_hog, h_mud, n_ren,
        count(*) AS records,
        count(*) FILTER (WHERE visit_number IS NOT NULL) AS valid_visit_records,
        min(visit_number) AS min_visit_number,
        max(visit_number) AS max_visit_number
    FROM records
    GROUP BY survey_year, survey_quarter, entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
), record_summary AS (
    SELECT
        survey_year,
        survey_quarter,
        count(*) AS records,
        count(*) FILTER (WHERE visit_number IS NOT NULL) AS valid_visit_records,
        count(*) FILTER (WHERE n_ent IS NULL) AS missing_visit_records,
        count(*) FILTER (WHERE n_ent IS NOT NULL AND visit_number IS NULL) AS invalid_visit_records
    FROM records
    GROUP BY survey_year, survey_quarter
), signature_summary AS (
    SELECT
        survey_year,
        survey_quarter,
        count(*) AS candidate_signatures,
        count(*) FILTER (WHERE records > 1) AS ambiguous_signature_groups
    FROM signatures
    GROUP BY survey_year, survey_quarter
), period_evidence AS (
    SELECT
        expected.period,
        coalesce(record_summary.records, 0) AS records,
        coalesce(record_summary.valid_visit_records, 0) AS valid_visit_records,
        coalesce(record_summary.missing_visit_records, 0) AS missing_visit_records,
        coalesce(record_summary.invalid_visit_records, 0) AS invalid_visit_records,
        coalesce(signature_summary.candidate_signatures, 0) AS candidate_signatures,
        coalesce(signature_summary.ambiguous_signature_groups, 0) AS ambiguous_signature_groups
    FROM expected_periods AS expected
    LEFT JOIN record_summary USING (survey_year, survey_quarter)
    LEFT JOIN signature_summary USING (survey_year, survey_quarter)
), period_pairs AS (
    SELECT
        current.period AS from_period,
        following.period AS to_period,
        current.survey_year AS from_year,
        current.survey_quarter AS from_quarter,
        following.survey_year AS to_year,
        following.survey_quarter AS to_quarter
    FROM expected_periods AS current
    JOIN expected_periods AS following
      ON (following.survey_year, following.survey_quarter) = (
          CASE WHEN current.survey_quarter = 4 THEN current.survey_year + 1
              ELSE current.survey_year END,
          CASE WHEN current.survey_quarter = 4 THEN 1 ELSE current.survey_quarter + 1 END
      )
), transition_evidence AS (
    SELECT
        pairs.from_period,
        pairs.to_period,
        count(previous.*) AS from_signature_groups,
        count(following.*) AS to_signature_groups,
        count(previous.*) FILTER (WHERE following.entity IS NOT NULL) AS shared_signatures,
        count(previous.*) FILTER (
            WHERE following.entity IS NOT NULL
              AND previous.records = 1
              AND following.records = 1
        ) AS unambiguous_shared_signatures,
        count(previous.*) FILTER (
            WHERE following.entity IS NOT NULL
              AND previous.records = 1
              AND following.records = 1
              AND previous.valid_visit_records = 1
              AND following.valid_visit_records = 1
              AND following.min_visit_number = previous.min_visit_number + 1
        ) AS expected_next_visit_signatures,
        count(previous.*) FILTER (
            WHERE following.entity IS NOT NULL
              AND previous.records = 1
              AND following.records = 1
              AND previous.valid_visit_records = 1
              AND following.valid_visit_records = 1
              AND following.min_visit_number <> previous.min_visit_number + 1
        ) AS mismatched_visit_signatures
    FROM period_pairs AS pairs
    LEFT JOIN signatures AS previous
      ON (previous.survey_year, previous.survey_quarter) = (pairs.from_year, pairs.from_quarter)
    LEFT JOIN signatures AS following
      ON (following.survey_year, following.survey_quarter) = (pairs.to_year, pairs.to_quarter)
     AND (following.entity, following.cd_a, following.con, following.v_sel, following.n_hog,
          following.h_mud, following.n_ren) =
         (previous.entity, previous.cd_a, previous.con, previous.v_sel, previous.n_hog,
          previous.h_mud, previous.n_ren)
    GROUP BY pairs.from_period, pairs.to_period
)
SELECT json_build_object(
    'candidate_signature', 'entity_cd_a_con_v_sel_n_hog_h_mud_n_ren',
    'candidate_signature_is_approved_linkage', false,
    'periods', (
        SELECT coalesce(json_agg(json_build_object(
            'period', period,
            'records', records,
            'valid_visit_records', valid_visit_records,
            'missing_visit_records', missing_visit_records,
            'invalid_visit_records', invalid_visit_records,
            'candidate_signatures', candidate_signatures,
            'ambiguous_signature_groups', ambiguous_signature_groups
        ) ORDER BY period), '[]'::json)
        FROM period_evidence
    ),
    'transitions', (
        SELECT coalesce(json_agg(json_build_object(
            'from_period', from_period,
            'to_period', to_period,
            'from_signature_groups', from_signature_groups,
            'to_signature_groups', to_signature_groups,
            'shared_signatures', shared_signatures,
            'unambiguous_shared_signatures', unambiguous_shared_signatures,
            'expected_next_visit_signatures', expected_next_visit_signatures,
            'mismatched_visit_signatures', mismatched_visit_signatures
        ) ORDER BY from_period), '[]'::json)
        FROM transition_evidence
    )
)::text;
"""


def _period_label(record: Mapping[str, object]) -> str:
    try:
        year = int(record["survey_year"])
        quarter = int(record["survey_quarter"])
    except (KeyError, TypeError, ValueError) as error:
        raise LongitudinalAuditError("record requires a numeric survey period") from error
    if quarter not in range(1, 5):
        raise LongitudinalAuditError("record has an invalid survey quarter")
    return f"{year}Q{quarter}"


def _next_period(period: str) -> str:
    year, quarter = int(period[:4]), int(period[-1])
    return f"{year + 1}Q1" if quarter == 4 else f"{year}Q{quarter + 1}"


def _role(period: str) -> str:
    year = int(period[:4])
    if year in (2023, 2024):
        return "development"
    if year == 2025:
        return "selection"
    if year == 2026:
        return "evaluation"
    return "outside_contract"


def _signature(record: Mapping[str, object]) -> tuple[str, ...]:
    try:
        values = tuple(str(record[field]).strip() for field in FOLLOWUP_SIGNATURE_FIELDS)
    except KeyError as error:
        raise LongitudinalAuditError(f"record lacks follow-up field: {error.args[0]}") from error
    if any(not value for value in values):
        raise LongitudinalAuditError("record has an incomplete candidate follow-up signature")
    return values


def _visit_number(value: object) -> int | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return int(rendered) if rendered in {"1", "2", "3", "4", "5"} else None


def audit_followup_records(
    records: Iterable[Mapping[str, object]], expected_periods: Sequence[str]
) -> dict[str, object]:
    """Return aggregate candidate-follow-up evidence without retaining any keys."""
    grouped: dict[str, dict[tuple[str, ...], list[tuple[str | None, int | None]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        period = _period_label(record)
        if period not in expected_periods:
            raise LongitudinalAuditError(f"record period is outside the requested audit: {period}")
        raw_visit = record.get("n_ent")
        normalized_visit = None if raw_visit is None else str(raw_visit).strip()
        grouped[period][_signature(record)].append(
            (normalized_visit or None, _visit_number(raw_visit))
        )

    evidence_periods = []
    for period in expected_periods:
        signatures = grouped[period]
        visits = [visit for group in signatures.values() for visit in group]
        evidence_periods.append(
            {
                "period": period,
                "records": len(visits),
                "valid_visit_records": sum(parsed is not None for _, parsed in visits),
                "missing_visit_records": sum(raw is None for raw, _ in visits),
                "invalid_visit_records": sum(
                    raw is not None and parsed is None for raw, parsed in visits
                ),
                "candidate_signatures": len(signatures),
                "ambiguous_signature_groups": sum(len(group) > 1 for group in signatures.values()),
            }
        )

    transitions = []
    for from_period in expected_periods:
        to_period = _next_period(from_period)
        if to_period not in expected_periods:
            continue
        previous = grouped[from_period]
        following = grouped[to_period]
        shared = set(previous).intersection(following)
        unambiguous = [
            signature
            for signature in shared
            if len(previous[signature]) == 1 and len(following[signature]) == 1
        ]
        expected = [
            signature
            for signature in unambiguous
            if previous[signature][0][1] is not None
            and following[signature][0][1] == previous[signature][0][1] + 1
        ]
        mismatched = [
            signature
            for signature in unambiguous
            if previous[signature][0][1] is not None
            and following[signature][0][1] is not None
            and following[signature][0][1] != previous[signature][0][1] + 1
        ]
        transitions.append(
            {
                "from_period": from_period,
                "to_period": to_period,
                "from_signature_groups": len(previous),
                "to_signature_groups": len(following),
                "shared_signatures": len(shared),
                "unambiguous_shared_signatures": len(unambiguous),
                "expected_next_visit_signatures": len(expected),
                "mismatched_visit_signatures": len(mismatched),
            }
        )

    boundaries = [
        {
            **transition,
            "from_role": _role(str(transition["from_period"])),
            "to_role": _role(str(transition["to_period"])),
        }
        for transition in transitions
        if _role(str(transition["from_period"])) != _role(str(transition["to_period"]))
    ]
    return {
        "candidate_signature": "entity_cd_a_con_v_sel_n_hog_h_mud_n_ren",
        "candidate_signature_is_approved_linkage": False,
        "periods": evidence_periods,
        "transitions": transitions,
        "role_boundaries": boundaries,
        "interpretation": (
            "candidate follow-up diagnostics only; matching signatures do not identify a person "
            "and do not authorize fitting, resampling, or exclusion"
        ),
    }


def validate_followup_evidence(
    evidence: Mapping[str, object], expected_periods: Sequence[str]
) -> dict[str, object]:
    """Fail closed on malformed evidence and report whether visit metadata is complete."""
    if evidence.get("candidate_signature_is_approved_linkage") is not False:
        raise LongitudinalAuditError("candidate signature must not be treated as person linkage")
    periods = evidence.get("periods")
    transitions = evidence.get("transitions")
    if not isinstance(periods, list) or not isinstance(transitions, list):
        raise LongitudinalAuditError("longitudinal audit returned malformed aggregate evidence")
    if tuple(period.get("period") for period in periods if isinstance(period, Mapping)) != tuple(
        expected_periods
    ):
        raise LongitudinalAuditError("longitudinal audit periods are incomplete or unexpected")
    blocking_reasons = []
    for period in periods:
        if not isinstance(period, Mapping):
            raise LongitudinalAuditError("longitudinal audit contains an invalid period row")
        for field in (
            "records",
            "valid_visit_records",
            "missing_visit_records",
            "invalid_visit_records",
            "candidate_signatures",
            "ambiguous_signature_groups",
        ):
            if not isinstance(period.get(field), int) or int(period[field]) < 0:
                raise LongitudinalAuditError(f"longitudinal audit has invalid {field}")
        if period["records"] == 0:
            blocking_reasons.append(f"{period['period']}: no staged candidate records")
        if period["missing_visit_records"] or period["invalid_visit_records"]:
            blocking_reasons.append(f"{period['period']}: visit metadata requires reload or review")
    return {
        **dict(evidence),
        "leakage_exclusion_approved": False,
        "visit_metadata_complete": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
    }


def audit_core_staging() -> dict[str, object]:
    """Audit core staging with SQL aggregates only; never return a source record or key."""
    try:
        evidence = json.loads(database_sql(CORE_AUDIT_SQL))
    except json.JSONDecodeError as error:
        raise LongitudinalAuditError("core longitudinal audit did not return JSON") from error
    if not isinstance(evidence, dict):
        raise LongitudinalAuditError("core longitudinal audit returned invalid evidence")
    evidence["role_boundaries"] = [
        {
            **transition,
            "from_role": _role(str(transition["from_period"])),
            "to_role": _role(str(transition["to_period"])),
        }
        for transition in evidence.get("transitions", [])
        if isinstance(transition, Mapping)
        and _role(str(transition["from_period"])) != _role(str(transition["to_period"]))
    ]
    return validate_followup_evidence(evidence, CORE_PERIODS)


def _evaluation_paths(data_dir: Path) -> dict[Period, Path]:
    return {period: data_dir / period.archive_name for period in EVALUATION_PERIODS}


def audit_evaluation_archives(data_dir: Path) -> dict[str, object]:
    """Audit the selection-to-evaluation boundary from official archives in memory only."""
    reference_path = data_dir / REFERENCE_PERIOD.archive_name
    evaluation_paths = _evaluation_paths(data_dir)
    integrity = audit_temporal_evaluation(reference_path, evaluation_paths)
    validated = [validate_archive(REFERENCE_PERIOD, reference_path)] + [
        validate_archive(period, evaluation_paths[period]) for period in EVALUATION_PERIODS
    ]
    records = [record for period in validated for record in period.records]
    evidence = audit_followup_records(records, EVALUATION_AUDIT_PERIODS)
    result = validate_followup_evidence(evidence, EVALUATION_AUDIT_PERIODS)
    return {
        **result,
        "evaluation_archive_integrity_decision": integrity["decision"],
        "source_scope": "official archives in memory only; 2026 remains outside staging and fitting",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-core")
    evaluation = commands.add_parser("audit-evaluation")
    evaluation.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    args = parser.parse_args()

    result = (
        audit_core_staging()
        if args.command == "audit-core"
        else audit_evaluation_archives(args.data_dir)
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
