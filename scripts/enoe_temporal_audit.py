#!/usr/bin/env python3
"""Audit official ENOE 2026 files for separate temporal-evaluation eligibility."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from zipfile import ZipFile

if __package__:
    from scripts.enoe_ingest import (
        ENTITY_ALIASES,
        REQUIRED_FIELDS,
        Period,
        _headers,
        download,
        validate_archive,
    )
else:
    from enoe_ingest import (
        ENTITY_ALIASES,
        REQUIRED_FIELDS,
        Period,
        _headers,
        download,
        validate_archive,
    )

REFERENCE_PERIOD = Period(2025, 4)
EVALUATION_PERIODS = (Period(2026, 1), Period(2026, 2))
PROFILE_SOURCE_FIELDS = (
    "r_def",
    "c_res",
    "eda",
    "clase2",
    "pos_ocu",
    "rama",
    "c_ocu11c",
    "fac_tri",
    "ing7c",
    "dur9c",
    "emple7c",
    "tip_con",
    "seg_soc",
    "pre_asa",
    "tue_ppal",
    "emp_ppal",
)
VALID_CODES = {
    "pos_ocu": frozenset({"1", "2", "3", "4", "5"}),
    "rama": frozenset({"1", "2", "3", "4", "5", "6", "7"}),
    "c_ocu11c": frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"}),
    "ing7c": frozenset({"1", "2", "3", "4", "5", "6", "7"}),
    "dur9c": frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9"}),
    "emple7c": frozenset({"1", "2", "3", "4", "5", "6", "7"}),
    "tip_con": frozenset({"1", "2", "3", "4", "5", "6"}),
    "seg_soc": frozenset({"1", "2", "3"}),
    "pre_asa": frozenset({"1", "2", "3"}),
    "tue_ppal": frozenset({"1", "2"}),
    "emp_ppal": frozenset({"1", "2"}),
}


class TemporalAuditError(ValueError):
    """Raised when an evaluation archive is unsafe for temporal comparison."""


def parse_evaluation_period(value: str) -> Period:
    """Accept only the separately governed 2026 temporal-evaluation window."""
    try:
        period = Period(int(value[:4]), int(value[5:]))
    except ValueError as error:
        raise argparse.ArgumentTypeError("period must be YYYYQn") from error
    if len(value) != 6 or value[4].upper() != "Q" or period not in EVALUATION_PERIODS:
        raise argparse.ArgumentTypeError("period must be 2026Q1 or 2026Q2")
    return period


def _normalized_headers(archive_path: Path) -> dict[str, set[str]]:
    with ZipFile(archive_path) as archive:
        return {
            prefix: {
                "entity" if field in ENTITY_ALIASES else field
                for field in _headers(archive, prefix)
            }
            for prefix in REQUIRED_FIELDS
        }


def _schema_comparison(reference_path: Path, evaluation_path: Path) -> dict[str, dict[str, object]]:
    reference = _normalized_headers(reference_path)
    evaluation = _normalized_headers(evaluation_path)
    return {
        prefix: {
            "added_fields": sorted(evaluation[prefix] - reference[prefix]),
            "removed_fields": sorted(reference[prefix] - evaluation[prefix]),
            "required_fields_present": {
                "entity" if field == "entity" else field for field in REQUIRED_FIELDS[prefix]
            }
            <= evaluation[prefix],
        }
        for prefix in REQUIRED_FIELDS
    }


def _field_coverage(records: Iterable[dict[str, object]]) -> dict[str, dict[str, int]]:
    rows = list(records)
    return {
        field: {
            "observed_records": sum(record.get(field) is not None for record in rows),
            "missing_records": sum(record.get(field) is None for record in rows),
        }
        for field in PROFILE_SOURCE_FIELDS
    }


def _invalid_codes(records: Iterable[dict[str, object]]) -> dict[str, int]:
    rows = list(records)
    return {
        field: sum(
            record.get(field) is not None and str(record[field]) not in allowed for record in rows
        )
        for field, allowed in VALID_CODES.items()
    }


def audit_temporal_evaluation(
    reference_path: Path, evaluation_paths: dict[Period, Path]
) -> dict[str, object]:
    """Validate 2026 sources without loading or extending the core staging window."""
    if set(evaluation_paths) != set(EVALUATION_PERIODS):
        raise TemporalAuditError("audit requires exactly 2026Q1 and 2026Q2 archives")
    validate_archive(REFERENCE_PERIOD, reference_path)

    periods = []
    for period in EVALUATION_PERIODS:
        validated = validate_archive(period, evaluation_paths[period])
        coverage = _field_coverage(validated.records)
        invalid_codes = _invalid_codes(validated.records)
        empty_fields = [
            field for field, counts in coverage.items() if counts["observed_records"] == 0
        ]
        invalid_fields = [field for field, count in invalid_codes.items() if count]
        if empty_fields or invalid_fields:
            details = []
            if empty_fields:
                details.append("empty fields: " + ", ".join(empty_fields))
            if invalid_fields:
                details.append("invalid codes: " + ", ".join(invalid_fields))
            raise TemporalAuditError(
                f"{period.label} is unsafe for temporal evaluation: " + "; ".join(details)
            )
        periods.append(
            {
                "period": period.label,
                "provenance": {
                    "archive_name": validated.archive.name,
                    "byte_size": validated.byte_size,
                    "sha256": validated.sha256,
                    "official_url": period.url,
                },
                "source_rows": validated.audit["source_rows"],
                "candidate_records": validated.audit["candidate_records"],
                "candidate_positive_weight": validated.audit["candidate_positive_weight"],
                "unmatched_candidate_records": validated.audit["unmatched_candidate_records"],
                "field_coverage": coverage,
                "invalid_codes": invalid_codes,
                "schema_comparison_to_2025Q4": _schema_comparison(
                    reference_path, evaluation_paths[period]
                ),
            }
        )
    return {
        "decision": "source_integrity_passed_for_separate_temporal_evaluation",
        "reference_period": REFERENCE_PERIOD.label,
        "evaluation_periods": periods,
        "scope_limit": "2026 remains outside the 2023Q1--2025Q4 core profile and baseline window",
    }


def _archive_paths(data_dir: Path) -> dict[Period, Path]:
    return {period: data_dir / period.archive_name for period in EVALUATION_PERIODS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download_parser = commands.add_parser("download")
    download_parser.add_argument("period", type=parse_evaluation_period)
    download_parser.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    args = parser.parse_args()

    if args.command == "download":
        archive = download(args.period, args.data_dir)
        print(json.dumps({"period": args.period.label, "archive": archive.name}, sort_keys=True))
        return

    reference_path = args.data_dir / REFERENCE_PERIOD.archive_name
    print(
        json.dumps(
            audit_temporal_evaluation(reference_path, _archive_paths(args.data_dir)), indent=2
        )
    )


if __name__ == "__main__":
    main()
