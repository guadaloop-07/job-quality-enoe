#!/usr/bin/env python3
"""Audit ENOE SDEM-COE joins from local official ZIP archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

OFFICIAL_JOIN_KEY = (
    "tipo",
    "mes_cal",
    "cd_a",
    "entity",
    "con",
    "v_sel",
    "n_hog",
    "h_mud",
    "n_ren",
)
CURRENT_STORAGE_KEY = (
    "cd_a",
    "entity",
    "con",
    "v_sel",
    "n_hog",
    "h_mud",
    "n_ent",
    "n_ren",
)
CURRENT_ETL_JOIN_KEY = CURRENT_STORAGE_KEY
ENTITY_ALIASES = ("ent", "cve_ent")
OFFICIAL_BASE_URL = (
    "https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/"
    "enoe_{year}_trim{quarter}_csv.zip"
)


class AuditError(ValueError):
    """Raised when an archive cannot be audited safely."""


@dataclass(frozen=True)
class Source:
    year: int
    quarter: int
    path: Path

    @property
    def period(self) -> str:
        return f"{self.year}Q{self.quarter}"


def parse_source(value: str) -> Source:
    """Parse YYYYQn=/path/to/archive.zip without guessing a period."""
    try:
        period, raw_path = value.split("=", 1)
        year = int(period[:4])
        quarter = int(period[5:])
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("source must be YYYYQn=/path/to/archive.zip") from error
    if len(period) != 6 or period[4].upper() != "Q" or quarter not in range(1, 5):
        raise argparse.ArgumentTypeError("source must be YYYYQn=/path/to/archive.zip")
    path = Path(raw_path)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"archive does not exist: {path}")
    return Source(year=year, quarter=quarter, path=path)


def _find_csv(archive: ZipFile, prefix: str) -> str:
    candidates = [
        name
        for name in archive.namelist()
        if Path(name).name.upper().startswith(f"ENOE_{prefix}") and name.upper().endswith(".CSV")
    ]
    if len(candidates) != 1:
        raise AuditError(f"expected one ENOE_{prefix}*.csv, found {len(candidates)}")
    return candidates[0]


def _rows(archive: ZipFile, prefix: str) -> Iterable[dict[str, str]]:
    with archive.open(_find_csv(archive, prefix)) as binary:
        reader = csv.DictReader(io.TextIOWrapper(binary, encoding="latin-1", newline=""))
        if reader.fieldnames is None:
            raise AuditError(f"{prefix} has no header")
        headers = [name.strip().lower() for name in reader.fieldnames]
        if len(headers) != len(set(headers)):
            raise AuditError(f"{prefix} has duplicate normalized columns")
        reader.fieldnames = headers
        for row in reader:
            yield {name: (value or "").strip() for name, value in row.items()}


def _headers(archive: ZipFile, prefix: str) -> tuple[str, ...]:
    with archive.open(_find_csv(archive, prefix)) as binary:
        reader = csv.reader(io.TextIOWrapper(binary, encoding="latin-1", newline=""))
        try:
            return tuple(name.strip().lower() for name in next(reader))
        except StopIteration as error:
            raise AuditError(f"{prefix} is empty") from error


def _entity_column(headers: Iterable[str], prefix: str) -> str:
    matches = [name for name in ENTITY_ALIASES if name in headers]
    if len(matches) != 1:
        raise AuditError(f"{prefix} must contain exactly one of {ENTITY_ALIASES}")
    return matches[0]


def _require_columns(headers: Iterable[str], names: Iterable[str], prefix: str) -> None:
    available = set(headers)
    missing = [name for name in names if name != "entity" and name not in available]
    if missing:
        raise AuditError(f"{prefix} is missing required columns: {', '.join(missing)}")
    _entity_column(available, prefix)


def _value(row: dict[str, str], name: str) -> str:
    if name != "entity":
        return row.get(name, "")
    raw = row.get("ent") or row.get("cve_ent") or ""
    try:
        return str(int(raw))
    except ValueError:
        return raw


def _key(row: dict[str, str], names: Iterable[str]) -> tuple[str, ...]:
    return tuple(_value(row, name) for name in names)


def _integer(row: dict[str, str], name: str) -> int | None:
    try:
        return int(float(row.get(name, "")))
    except ValueError:
        return None


def _candidate(row: dict[str, str]) -> bool:
    age = _integer(row, "eda")
    return (
        _integer(row, "r_def") == 0
        and _integer(row, "c_res") in (1, 3)
        and age is not None
        and 15 <= age <= 98
        and _integer(row, "clase2") == 1
        and _integer(row, "pos_ocu") == 1
    )


def _duplicate_summary(rows: Iterable[dict[str, str]], names: Iterable[str]) -> dict[str, int]:
    counts = Counter(_key(row, names) for row in rows)
    return {
        "groups": sum(count > 1 for count in counts.values()),
        "excess_rows": sum(count - 1 for count in counts.values() if count > 1),
    }


def _missing_key_records(rows: Iterable[dict[str, str]], names: Iterable[str]) -> int:
    return sum(any(not value for value in _key(row, names)) for row in rows)


def _join_summary(
    candidates: list[dict[str, str]],
    counts: Counter,
    first: dict[tuple[str, ...], tuple[str, bool]],
    names: tuple[str, ...],
    target_entity: str,
) -> dict[str, int]:
    result = {
        "unmatched_records": 0,
        "unmatched_weight": 0,
        "multiple_match_records": 0,
        "multiple_match_weight": 0,
        "first_match_wrong_entity_records": 0,
        "first_match_wrong_entity_weight": 0,
        "first_match_blank_p3i_records": 0,
        "first_match_blank_p3i_weight": 0,
    }
    for row in candidates:
        row_key = _key(row, names)
        weight = _integer(row, "fac_tri") or 0
        matches = counts[row_key]
        if matches == 0:
            result["unmatched_records"] += 1
            result["unmatched_weight"] += weight
            continue
        if matches > 1:
            result["multiple_match_records"] += 1
            result["multiple_match_weight"] += weight
        entity, blank_p3i = first[row_key]
        if entity != target_entity:
            result["first_match_wrong_entity_records"] += 1
            result["first_match_wrong_entity_weight"] += weight
        if blank_p3i:
            result["first_match_blank_p3i_records"] += 1
            result["first_match_blank_p3i_weight"] += weight
    return result


def _audit_coe(
    archive: ZipFile,
    prefix: str,
    candidates: list[dict[str, str]],
    target_entity: str,
) -> dict:
    headers = _headers(archive, prefix)
    _require_columns(headers, OFFICIAL_JOIN_KEY, prefix)
    if prefix == "COE1":
        _require_columns(headers, ("p3i",), prefix)
    entity_column = _entity_column(headers, prefix)
    current_key = (
        CURRENT_ETL_JOIN_KEY
        if entity_column == "ent"
        else tuple(name for name in CURRENT_ETL_JOIN_KEY if name != "entity")
    )

    official_counts: Counter = Counter()
    official_first: dict[tuple[str, ...], tuple[str, bool]] = {}
    current_counts: Counter = Counter()
    current_first: dict[tuple[str, ...], tuple[str, bool]] = {}
    entity_rows = 0
    missing_official_keys = 0

    for row in _rows(archive, prefix):
        entity = _value(row, "entity")
        blank_p3i = prefix == "COE1" and not row.get("p3i", "")
        current_row_key = _key(row, current_key)
        current_counts[current_row_key] += 1
        current_first.setdefault(current_row_key, (entity, blank_p3i))
        if entity != target_entity:
            continue
        entity_rows += 1
        official_row_key = _key(row, OFFICIAL_JOIN_KEY)
        if any(not value for value in official_row_key):
            missing_official_keys += 1
        official_counts[official_row_key] += 1
        official_first.setdefault(official_row_key, (entity, blank_p3i))

    official_duplicates = {
        "groups": sum(count > 1 for count in official_counts.values()),
        "excess_rows": sum(count - 1 for count in official_counts.values() if count > 1),
    }
    official_join = _join_summary(
        candidates, official_counts, official_first, OFFICIAL_JOIN_KEY, target_entity
    )
    current_join = _join_summary(
        candidates, current_counts, current_first, current_key, target_entity
    )
    official_safe = (
        missing_official_keys == 0
        and official_duplicates["groups"] == 0
        and official_join["unmatched_records"] == 0
        and official_join["multiple_match_records"] == 0
    )
    return {
        "entity_column": entity_column,
        "entity_rows": entity_rows,
        "missing_official_key_records": missing_official_keys,
        "official_key_duplicates": official_duplicates,
        "official_join": official_join,
        "official_join_safe": official_safe,
        "current_etl_join_key": list(current_key),
        "current_etl_key_conforms_to_official": current_key == OFFICIAL_JOIN_KEY,
        "current_etl_join": current_join,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_archive(source: Source, target_entity: int = 14) -> dict:
    target = str(target_entity)
    with ZipFile(source.path) as archive:
        headers = _headers(archive, "SDEM")
        _require_columns(headers, OFFICIAL_JOIN_KEY, "SDEM")
        _require_columns(
            headers,
            ("r_def", "c_res", "eda", "clase2", "pos_ocu", "fac_tri"),
            "SDEM",
        )
        entity_column = _entity_column(headers, "SDEM")
        entity_rows = [row for row in _rows(archive, "SDEM") if _value(row, "entity") == target]
        candidates = [row for row in entity_rows if _candidate(row)]
        official_duplicates = _duplicate_summary(candidates, OFFICIAL_JOIN_KEY)
        storage_duplicates = _duplicate_summary(candidates, CURRENT_STORAGE_KEY)
        missing_official_keys = _missing_key_records(candidates, OFFICIAL_JOIN_KEY)
        coe1 = _audit_coe(archive, "COE1", candidates, target)
        coe2 = _audit_coe(archive, "COE2", candidates, target)

    official_safe = (
        missing_official_keys == 0
        and official_duplicates["groups"] == 0
        and coe1["official_join_safe"]
        and coe2["official_join_safe"]
    )
    current_risk = (
        storage_duplicates["groups"] > 0
        or not coe1["current_etl_key_conforms_to_official"]
        or not coe2["current_etl_key_conforms_to_official"]
        or any(coe1["current_etl_join"].values())
        or any(coe2["current_etl_join"].values())
    )
    return {
        "period": source.period,
        "source": {
            "archive_name": source.path.name,
            "bytes": source.path.stat().st_size,
            "sha256": sha256(source.path),
            "official_url": OFFICIAL_BASE_URL.format(year=source.year, quarter=source.quarter),
        },
        "sdem": {
            "entity_column": entity_column,
            "entity_records": len(entity_rows),
            "candidate_records": len(candidates),
            "candidate_weight": sum(_integer(row, "fac_tri") or 0 for row in candidates),
            "missing_official_key_records": missing_official_keys,
            "official_key_duplicates": official_duplicates,
            "current_storage_key_duplicates": storage_duplicates,
        },
        "coe1": coe1,
        "coe2": coe2,
        "official_join_safe": official_safe,
        "current_pipeline_risk_detected": current_risk,
    }


def build_payload(sources: list[Source], target_entity: int = 14) -> dict:
    periods = [audit_archive(source, target_entity) for source in sources]
    return {
        "provenance": {
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "source": "official INEGI ENOE CSV ZIP archives",
            "scope": "aggregate join diagnostics; no microdata rows are emitted",
        },
        "target_entity": target_entity,
        "official_join_key": list(OFFICIAL_JOIN_KEY),
        "current_storage_key": list(CURRENT_STORAGE_KEY),
        "periods": periods,
        "official_sources_safe_to_join": all(period["official_join_safe"] for period in periods),
        "current_pipeline_risk_detected": any(
            period["current_pipeline_risk_detected"] for period in periods
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=parse_source, required=True)
    parser.add_argument("--entity", type=int, default=14)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = build_payload(args.source, args.entity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(payload, output, indent=2)
        output.write("\n")
    if not payload["official_sources_safe_to_join"]:
        raise SystemExit("official join safety checks failed; aggregate evidence was preserved")


if __name__ == "__main__":
    main()
