#!/usr/bin/env python3
"""Audit predeclared longitudinal split sensitivities without fitting a model."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

if __package__:
    from scripts.enoe_ingest import Period, validate_archive
    from scripts.enoe_longitudinal_audit import (
        FOLLOWUP_SIGNATURE_FIELDS,
        LongitudinalAuditError,
        _next_period,
        _period_label,
        _signature,
        _visit_number,
    )
    from scripts.enoe_temporal_audit import EVALUATION_PERIODS, audit_temporal_evaluation
    from scripts.profile_model_contract import (
        DEVELOPMENT_PERIODS,
        SELECTION_PERIODS,
        load_contract,
        validate_contract,
    )
    from scripts.profile_model_contract import (
        EVALUATION_PERIODS as CONTRACT_EVALUATION_PERIODS,
    )
else:
    from enoe_ingest import Period, validate_archive
    from enoe_longitudinal_audit import (
        FOLLOWUP_SIGNATURE_FIELDS,
        LongitudinalAuditError,
        _next_period,
        _period_label,
        _signature,
        _visit_number,
    )
    from enoe_temporal_audit import EVALUATION_PERIODS, audit_temporal_evaluation
    from profile_model_contract import (
        DEVELOPMENT_PERIODS,
        SELECTION_PERIODS,
        load_contract,
        validate_contract,
    )
    from profile_model_contract import (
        EVALUATION_PERIODS as CONTRACT_EVALUATION_PERIODS,
    )

ALL_PERIODS = DEVELOPMENT_PERIODS + SELECTION_PERIODS + CONTRACT_EVALUATION_PERIODS
MODES = ("primary", "sensitivity_a", "sensitivity_b")


class LongitudinalSensitivityError(ValueError):
    """Raised when longitudinal-sensitivity evidence cannot remain aggregate-only."""


def _role(period: str) -> str:
    if period in DEVELOPMENT_PERIODS:
        return "development"
    if period in SELECTION_PERIODS:
        return "selection"
    if period in CONTRACT_EVALUATION_PERIODS:
        return "evaluation"
    raise LongitudinalSensitivityError(f"period is outside the model contract: {period}")


def _weight(record: Mapping[str, object]) -> Decimal:
    value = record.get("analysis_weight", record.get("fac_tri"))
    try:
        weight = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise LongitudinalSensitivityError("record requires a numeric analysis weight") from error
    if weight <= 0:
        raise LongitudinalSensitivityError("record requires a positive analysis weight")
    return weight


def _group_records(
    records: Iterable[Mapping[str, object]], expected_periods: Sequence[str]
) -> dict[str, dict[tuple[str, ...], list[tuple[int | None, Decimal]]]]:
    grouped: dict[str, dict[tuple[str, ...], list[tuple[int | None, Decimal]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        try:
            period = _period_label(record)
            signature = _signature(record)
        except LongitudinalAuditError as error:
            raise LongitudinalSensitivityError(str(error)) from error
        if period not in expected_periods:
            raise LongitudinalSensitivityError(
                f"record period is outside the requested audit: {period}"
            )
        visit_number = _visit_number(record.get("n_ent"))
        if visit_number is None:
            raise LongitudinalSensitivityError(
                f"{period}: visit metadata requires reload or review before sensitivity analysis"
            )
        grouped[period][signature].append((visit_number, _weight(record)))
    return grouped


def _validated_boundary_signatures(
    grouped: Mapping[str, Mapping[tuple[str, ...], list[tuple[int | None, Decimal]]]],
    from_period: str,
    to_period: str,
) -> set[tuple[str, ...]]:
    if _next_period(from_period) != to_period:
        raise LongitudinalSensitivityError("primary boundary must join adjacent quarters")
    previous = grouped[from_period]
    following = grouped[to_period]
    return {
        signature
        for signature in set(previous).intersection(following)
        if len(previous[signature]) == 1
        and len(following[signature]) == 1
        and previous[signature][0][0] is not None
        and following[signature][0][0] == previous[signature][0][0] + 1
    }


def _prior_role_signatures(
    grouped: Mapping[str, Mapping[tuple[str, ...], list[tuple[int | None, Decimal]]]],
) -> dict[str, set[tuple[str, ...]]]:
    development = set().union(*(set(grouped[period]) for period in DEVELOPMENT_PERIODS))
    selection = set().union(*(set(grouped[period]) for period in SELECTION_PERIODS))
    return {
        "development": set(),
        "selection": development,
        "evaluation": development | selection,
    }


def audit_longitudinal_sensitivities(
    records: Iterable[Mapping[str, object]], expected_periods: Sequence[str] = ALL_PERIODS
) -> dict[str, object]:
    """Return aggregate eligibility effects for the fixed primary and sensitivity rules."""
    if tuple(expected_periods) != ALL_PERIODS:
        raise LongitudinalSensitivityError("audit requires the complete approved temporal window")
    grouped = _group_records(records, expected_periods)
    missing = [period for period in expected_periods if not grouped[period]]
    if missing:
        raise LongitudinalSensitivityError(
            "audit has missing period records: " + ", ".join(missing)
        )

    primary_excluded = {
        "development": set(),
        "selection": _validated_boundary_signatures(grouped, "2024Q4", "2025Q1"),
        "evaluation": _validated_boundary_signatures(grouped, "2025Q4", "2026Q1"),
    }
    conservative_excluded = _prior_role_signatures(grouped)
    rows = []
    for period in expected_periods:
        role = _role(period)
        for mode in MODES:
            excluded_signatures = (
                set()
                if mode == "sensitivity_a"
                else primary_excluded[role]
                if mode == "primary"
                else conservative_excluded[role]
            )
            all_records = [
                (signature, weight)
                for signature, visits in grouped[period].items()
                for _, weight in visits
            ]
            excluded = [
                weight for signature, weight in all_records if signature in excluded_signatures
            ]
            total_weight = sum((weight for _, weight in all_records), Decimal())
            excluded_weight = sum(excluded, Decimal())
            rows.append(
                {
                    "mode": mode,
                    "period": period,
                    "period_role": role,
                    "input_records": len(all_records),
                    "eligible_records": len(all_records) - len(excluded),
                    "excluded_records": len(excluded),
                    "input_positive_weight": str(total_weight),
                    "eligible_positive_weight": str(total_weight - excluded_weight),
                    "excluded_positive_weight": str(excluded_weight),
                }
            )
    return {
        "fit_authorized": False,
        "candidate_signature": "_".join(FOLLOWUP_SIGNATURE_FIELDS),
        "candidate_signature_is_approved_linkage": False,
        "analysis_hierarchy": {
            "primary": "model_selection_only",
            "sensitivity_a": "fixed_solution_robustness_only",
            "sensitivity_b": "fixed_solution_robustness_only",
        },
        "primary_boundary_anchor_counts": {
            "development_to_selection": len(primary_excluded["selection"]),
            "selection_to_evaluation": len(primary_excluded["evaluation"]),
        },
        "periods": rows,
        "interpretation": (
            "aggregate eligibility evidence only; candidate signatures are not nominal linkage "
            "and no fitting, resampling, or input materialization is authorized"
        ),
    }


def validate_sensitivity_evidence(evidence: Mapping[str, object]) -> dict[str, object]:
    """Validate aggregate accounting and keep every split in pre-fit status."""
    if evidence.get("fit_authorized") is not False:
        raise LongitudinalSensitivityError("longitudinal sensitivities must not authorize fitting")
    if evidence.get("candidate_signature_is_approved_linkage") is not False:
        raise LongitudinalSensitivityError(
            "candidate signature must not be treated as person linkage"
        )
    periods = evidence.get("periods")
    if not isinstance(periods, list) or len(periods) != len(ALL_PERIODS) * len(MODES):
        raise LongitudinalSensitivityError(
            "longitudinal sensitivity evidence has incomplete periods"
        )
    expected = {(mode, period) for mode in MODES for period in ALL_PERIODS}
    observed = set()
    for row in periods:
        if not isinstance(row, Mapping):
            raise LongitudinalSensitivityError(
                "longitudinal sensitivity evidence has an invalid row"
            )
        mode, period = row.get("mode"), row.get("period")
        if not isinstance(mode, str) or not isinstance(period, str):
            raise LongitudinalSensitivityError(
                "longitudinal sensitivity evidence lacks mode or period"
            )
        observed.add((mode, period))
        counts = ("input_records", "eligible_records", "excluded_records")
        if any(not isinstance(row.get(field), int) or int(row[field]) < 0 for field in counts):
            raise LongitudinalSensitivityError(
                "longitudinal sensitivity evidence has invalid counts"
            )
        if row["input_records"] != row["eligible_records"] + row["excluded_records"]:
            raise LongitudinalSensitivityError(
                "longitudinal sensitivity record counts do not reconcile"
            )
        try:
            input_weight = Decimal(str(row["input_positive_weight"]))
            eligible_weight = Decimal(str(row["eligible_positive_weight"]))
            excluded_weight = Decimal(str(row["excluded_positive_weight"]))
        except (InvalidOperation, KeyError, ValueError) as error:
            raise LongitudinalSensitivityError(
                "longitudinal sensitivity evidence has invalid weights"
            ) from error
        if input_weight <= 0 or input_weight != eligible_weight + excluded_weight:
            raise LongitudinalSensitivityError("longitudinal sensitivity weights do not reconcile")
    if observed != expected:
        raise LongitudinalSensitivityError(
            "longitudinal sensitivity evidence has unexpected modes or periods"
        )
    return dict(evidence)


def _archive_paths(data_dir: Path) -> dict[Period, Path]:
    return {
        Period(int(period[:4]), int(period[-1])): data_dir
        / Period(int(period[:4]), int(period[-1])).archive_name
        for period in ALL_PERIODS
    }


def audit_official_archives(data_dir: Path) -> dict[str, object]:
    """Read official archives in memory and return only aggregate sensitivity evidence."""
    validate_contract(load_contract())
    paths = _archive_paths(data_dir)
    reference = Period(2025, 4)
    evaluation_paths = {period: paths[period] for period in EVALUATION_PERIODS}
    integrity = audit_temporal_evaluation(paths[reference], evaluation_paths)
    records = []
    for period in sorted(paths, key=lambda item: (item.year, item.quarter)):
        records.extend(validate_archive(period, paths[period]).records)
    evidence = validate_sensitivity_evidence(audit_longitudinal_sensitivities(records))
    return {
        **evidence,
        "evaluation_archive_integrity_decision": integrity["decision"],
        "source_scope": "official archives in memory only; 2026 remains outside staging and fitting",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    args = parser.parse_args()
    print(json.dumps(audit_official_archives(args.data_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
