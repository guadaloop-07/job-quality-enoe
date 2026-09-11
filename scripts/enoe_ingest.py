#!/usr/bin/env python3
"""Download, validate, and load official ENOE CSV archives into local staging."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

if __package__:
    from scripts.migrate_database import command as database_command
else:
    from migrate_database import command as database_command

OFFICIAL_BASE_URL = (
    "https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/"
    "enoe_{year}_trim{quarter}_csv.zip"
)
TARGET_ENTITY = 14
CORE_PERIODS = tuple((year, quarter) for year in range(2023, 2026) for quarter in range(1, 5))
ENTITY_ALIASES = ("ent", "cve_ent")
OFFICIAL_KEY = ("tipo", "mes_cal", "cd_a", "entity", "con", "v_sel", "n_hog", "h_mud", "n_ren")
SDEM_FIELDS = (
    "r_def",
    "c_res",
    "eda",
    "clase2",
    "pos_ocu",
    "fac_tri",
    "est_d_tri",
    "upm",
    "remune2c",
    "ingocup",
    "ing7c",
    "hrsocup",
    "dur9c",
    "tip_con",
    "seg_soc",
    "pre_asa",
    "medica5c",
    "tue_ppal",
    "emp_ppal",
)
REQUIRED_FIELDS = {
    "SDEM": OFFICIAL_KEY + SDEM_FIELDS,
    "COE1": OFFICIAL_KEY + ("p3i",),
    "COE2": OFFICIAL_KEY,
}
COPY_COLUMNS = (
    "survey_year",
    "survey_quarter",
    *OFFICIAL_KEY,
    *SDEM_FIELDS,
    "p3i",
    "source_archive_sha256",
)


class IngestionError(ValueError):
    """Raised when source evidence is insufficient for a safe load."""


@dataclass(frozen=True)
class Period:
    year: int
    quarter: int

    @property
    def label(self) -> str:
        return f"{self.year}Q{self.quarter}"

    @property
    def archive_name(self) -> str:
        return f"enoe_{self.year}_trim{self.quarter}_csv.zip"

    @property
    def url(self) -> str:
        return OFFICIAL_BASE_URL.format(year=self.year, quarter=self.quarter)


@dataclass
class ValidatedPeriod:
    period: Period
    archive: Path
    sha256: str
    byte_size: int
    retrieved_at_utc: str
    records: list[dict[str, str | Decimal | None]]
    audit: dict[str, object]


def parse_period(value: str) -> Period:
    try:
        year = int(value[:4])
        quarter = int(value[5:])
    except ValueError as error:
        raise argparse.ArgumentTypeError("period must be YYYYQn") from error
    if len(value) != 6 or value[4].upper() != "Q" or quarter not in range(1, 5):
        raise argparse.ArgumentTypeError("period must be YYYYQn")
    if (year, quarter) not in CORE_PERIODS:
        raise argparse.ArgumentTypeError("period must be in the 2023Q1--2025Q4 core window")
    return Period(year, quarter)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(value: str | None) -> str:
    return (value or "").strip()


def integer(value: str | None) -> int | None:
    try:
        parsed = Decimal(normalized(value))
    except InvalidOperation:
        return None
    return int(parsed) if parsed == parsed.to_integral_value() else None


def decimal(value: str | None) -> Decimal | None:
    try:
        return Decimal(normalized(value))
    except InvalidOperation:
        return None


def entity_value(row: dict[str, str]) -> str:
    value = normalized(row.get("ent") or row.get("cve_ent"))
    parsed = integer(value)
    return str(parsed) if parsed is not None else value


def key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        entity_value(row) if name == "entity" else normalized(row.get(name))
        for name in OFFICIAL_KEY
    )


def _table_name(archive: ZipFile, prefix: str) -> str:
    matches = [
        name
        for name in archive.namelist()
        if Path(name).name.upper().startswith(f"ENOE_{prefix}") and name.upper().endswith(".CSV")
    ]
    if len(matches) != 1:
        raise IngestionError(f"{prefix}: expected one CSV table, found {len(matches)}")
    return matches[0]


def _headers(archive: ZipFile, prefix: str) -> tuple[str, ...]:
    with archive.open(_table_name(archive, prefix)) as binary:
        reader = csv.reader(io.TextIOWrapper(binary, encoding="latin-1", newline=""))
        try:
            fields = tuple(normalized(value).lower() for value in next(reader))
        except StopIteration as error:
            raise IngestionError(f"{prefix}: empty CSV table") from error
    if len(fields) != len(set(fields)):
        raise IngestionError(f"{prefix}: duplicate normalized headers")
    aliases = set(fields).intersection(ENTITY_ALIASES)
    if len(aliases) != 1:
        raise IngestionError(f"{prefix}: require exactly one entity alias, ENT or CVE_ENT")
    missing = [
        field for field in REQUIRED_FIELDS[prefix] if field != "entity" and field not in fields
    ]
    if missing:
        raise IngestionError(f"{prefix}: missing required columns: {', '.join(missing)}")
    return fields


def _rows(archive: ZipFile, prefix: str):
    _headers(archive, prefix)
    with archive.open(_table_name(archive, prefix)) as binary:
        reader = csv.DictReader(io.TextIOWrapper(binary, encoding="latin-1", newline=""))
        reader.fieldnames = [normalized(value).lower() for value in reader.fieldnames or ()]
        for row in reader:
            if None in row:
                raise IngestionError(f"{prefix}: a row has more values than headers")
            yield {name: normalized(value) for name, value in row.items()}


def candidate(row: dict[str, str]) -> bool:
    age = integer(row.get("eda"))
    return (
        integer(row.get("r_def")) == 0
        and integer(row.get("c_res")) in (1, 3)
        and age is not None
        and 15 <= age <= 98
        and integer(row.get("clase2")) == 1
        and integer(row.get("pos_ocu")) == 1
    )


def _check_source_keys(rows: list[dict[str, str]], prefix: str) -> Counter[tuple[str, ...]]:
    keys = [key(row) for row in rows]
    if any(any(not component for component in value) for value in keys):
        raise IngestionError(f"{prefix}: target-entity records have incomplete official keys")
    counts = Counter(keys)
    duplicate_groups = sum(count > 1 for count in counts.values())
    if duplicate_groups:
        raise IngestionError(f"{prefix}: {duplicate_groups} duplicate official-key groups")
    return counts


def validate_archive(
    period: Period, archive_path: Path, target_entity: int = TARGET_ENTITY
) -> ValidatedPeriod:
    """Validate all required source tables before constructing any persisted row."""
    if not archive_path.is_file():
        raise IngestionError(f"archive does not exist: {archive_path}")
    target = str(target_entity)
    with ZipFile(archive_path) as archive:
        tables = {
            prefix: [row for row in _rows(archive, prefix) if entity_value(row) == target]
            for prefix in REQUIRED_FIELDS
        }
    counts = {prefix: _check_source_keys(rows, prefix) for prefix, rows in tables.items()}
    candidates = [row for row in tables["SDEM"] if candidate(row)]
    if not candidates:
        raise IngestionError("SDEM: no rows satisfy the Jalisco candidate universe")
    candidate_keys = [key(row) for row in candidates]
    unmatched = {
        prefix: sum(candidate_key not in counts[prefix] for candidate_key in candidate_keys)
        for prefix in ("COE1", "COE2")
    }
    if any(unmatched.values()):
        raise IngestionError(
            "candidate COE matches are incomplete: "
            + ", ".join(f"{prefix}={count}" for prefix, count in unmatched.items())
        )
    coe1 = {key(row): row for row in tables["COE1"]}
    records: list[dict[str, str | Decimal | None]] = []
    weight = Decimal("0")
    for sdem in candidates:
        fac_tri = decimal(sdem.get("fac_tri"))
        if fac_tri is None or fac_tri <= 0:
            raise IngestionError("SDEM: candidate rows require a positive numeric FAC_TRI")
        weight += fac_tri
        row_key = key(sdem)
        record: dict[str, str | Decimal | None] = {
            "survey_year": str(period.year),
            "survey_quarter": str(period.quarter),
            **dict(zip(OFFICIAL_KEY, row_key, strict=True)),
            **{field: sdem.get(field) or None for field in SDEM_FIELDS},
            "p3i": coe1[row_key].get("p3i") or None,
        }
        record["fac_tri"] = fac_tri
        records.append(record)
    records.sort(key=lambda record: tuple(str(record[field]) for field in OFFICIAL_KEY))
    archive_sha256 = sha256(archive_path)
    for record in records:
        record["source_archive_sha256"] = archive_sha256
    audit = {
        "period": period.label,
        "target_entity": target_entity,
        "source_rows": {prefix: len(rows) for prefix, rows in tables.items()},
        "candidate_records": len(records),
        "candidate_positive_weight": str(weight),
        "unmatched_candidate_records": unmatched,
        "official_key_duplicate_groups": {prefix: 0 for prefix in REQUIRED_FIELDS},
    }
    return ValidatedPeriod(
        period=period,
        archive=archive_path,
        sha256=archive_sha256,
        byte_size=archive_path.stat().st_size,
        retrieved_at_utc=datetime.fromtimestamp(archive_path.stat().st_mtime, UTC).isoformat(),
        records=records,
        audit=audit,
    )


def payload(validated: ValidatedPeriod) -> dict[str, object]:
    return {
        "provenance": {
            "source": "official INEGI ENOE CSV ZIP archive",
            "official_url": validated.period.url,
            "archive_name": validated.archive.name,
            "byte_size": validated.byte_size,
            "sha256": validated.sha256,
            "retrieved_at_utc": validated.retrieved_at_utc,
        },
        "audit": validated.audit,
    }


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _copy_data(records: list[dict[str, str | Decimal | None]]) -> str:
    target = io.StringIO()
    writer = csv.writer(target, lineterminator="\n")
    for record in records:
        writer.writerow(
            ["" if record.get(column) is None else record[column] for column in COPY_COLUMNS]
        )
    return target.getvalue()


def _revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True, timeout=10
    )
    revision = result.stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], text=True, capture_output=True, check=True, timeout=10
    )
    return revision if not status.stdout else revision + "-dirty"


def transaction_sql(validated: ValidatedPeriod) -> str:
    """Build one atomic replacement transaction without logging microdata."""
    details = json.dumps(payload(validated), sort_keys=True)
    source = validated.period
    weight = Decimal(str(validated.audit["candidate_positive_weight"]))
    columns = ", ".join(COPY_COLUMNS)
    return f"""BEGIN;
LOCK TABLE staging.enoe_person_quarter IN SHARE ROW EXCLUSIVE MODE;
DELETE FROM staging.enoe_person_quarter
WHERE survey_year = {source.year} AND survey_quarter = {source.quarter};
COPY staging.enoe_person_quarter ({columns}) FROM STDIN WITH (FORMAT csv, NULL '');
{_copy_data(validated.records)}\\.
DO $$
DECLARE persisted_rows bigint; persisted_weight numeric;
BEGIN
    SELECT count(*), coalesce(sum(fac_tri), 0)
    INTO persisted_rows, persisted_weight
    FROM staging.enoe_person_quarter
    WHERE survey_year = {source.year} AND survey_quarter = {source.quarter};
    IF persisted_rows <> {len(validated.records)} OR persisted_weight <> {weight} THEN
        RAISE EXCEPTION 'staging reconciliation failed';
    END IF;
END $$;
INSERT INTO metadata.source_archives (
    source_name, archive_name, survey_year, survey_quarter, download_url, content_sha256,
    byte_size, retrieved_at_utc
) VALUES (
    'INEGI ENOE 15 and over CSV', {_sql_literal(validated.archive.name)}, {source.year},
    {source.quarter}, {_sql_literal(source.url)}, {_sql_literal(validated.sha256)},
    {validated.byte_size}, {_sql_literal(validated.retrieved_at_utc)}::timestamptz
)
ON CONFLICT (source_name, survey_year, survey_quarter, content_sha256) DO UPDATE
SET archive_name = EXCLUDED.archive_name,
    byte_size = EXCLUDED.byte_size,
    retrieved_at_utc = EXCLUDED.retrieved_at_utc;
INSERT INTO metadata.ingestion_runs (
    archive_id, pipeline_revision, completed_at_utc, status, details
)
SELECT archive_id, {_sql_literal(_revision())}, now(), 'succeeded', {_sql_literal(details)}::jsonb
FROM metadata.source_archives
WHERE source_name = 'INEGI ENOE 15 and over CSV'
  AND survey_year = {source.year}
  AND survey_quarter = {source.quarter}
  AND content_sha256 = {_sql_literal(validated.sha256)};
COMMIT;
"""


def database_sql(sql: str) -> str:
    result = subprocess.run(
        database_command(), input=sql, text=True, capture_output=True, timeout=300
    )
    if result.returncode:
        raise IngestionError("database transaction failed; the period was rolled back")
    return result.stdout


def load(validated: ValidatedPeriod) -> dict[str, object]:
    database_sql(transaction_sql(validated))
    return payload(validated)


def staging_audit(validated: ValidatedPeriod) -> dict[str, object]:
    period = validated.period
    rows = (
        database_sql(
            f"SELECT count(*), coalesce(sum(fac_tri), 0) FROM staging.enoe_person_quarter "
            f"WHERE survey_year = {period.year} AND survey_quarter = {period.quarter};"
        )
        .strip()
        .split("|")
    )
    persisted_records, persisted_weight = int(rows[0]), Decimal(rows[1])
    expected_records = len(validated.records)
    expected_weight = Decimal(str(validated.audit["candidate_positive_weight"]))
    result = {
        "period": period.label,
        "raw_candidate_records": expected_records,
        "staged_candidate_records": persisted_records,
        "raw_candidate_positive_weight": str(expected_weight),
        "staged_candidate_positive_weight": str(persisted_weight),
        "reconciled": expected_records == persisted_records and expected_weight == persisted_weight,
    }
    if not result["reconciled"]:
        raise IngestionError("raw and staged candidate aggregates do not reconcile")
    return result


def download(period: Period, data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / period.archive_name
    if target.exists():
        return target
    with tempfile.NamedTemporaryFile(dir=data_dir, suffix=".part", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        request = Request(period.url, headers={"User-Agent": "job-quality-enoe/0.1"})
        with urlopen(request, timeout=180) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                temporary.write(chunk)
    temporary_path.replace(target)
    return target


def write_payload(value: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True)
    if output is None:
        print(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(rendered + "\n")


def manifest(data_dir: Path) -> dict[str, object]:
    """Return reproducible official-source metadata without reading survey rows."""
    sources = []
    for year, quarter in CORE_PERIODS:
        period = Period(year, quarter)
        archive = data_dir / period.archive_name
        if not archive.is_file():
            raise IngestionError(f"archive is missing from the core manifest: {archive}")
        sources.append(
            {
                "period": period.label,
                "official_url": period.url,
                "archive_name": archive.name,
                "byte_size": archive.stat().st_size,
                "sha256": sha256(archive),
                "retrieved_at_utc": datetime.fromtimestamp(
                    archive.stat().st_mtime, UTC
                ).isoformat(),
            }
        )
    return {"source": "official INEGI ENOE CSV archives", "periods": sources}


def _archive_for(args: argparse.Namespace) -> Path:
    if args.archive:
        return args.archive
    return args.data_dir / args.period.archive_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("download", "validate", "ingest", "audit-staging"):
        command = commands.add_parser(name)
        command.add_argument("period", type=parse_period)
        command.add_argument("--archive", type=Path)
        command.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
        if name == "validate":
            command.add_argument("--output", type=Path)
    all_command = commands.add_parser("ingest-all")
    all_command.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    audit_all_command = commands.add_parser("audit-all")
    audit_all_command.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    commands.add_parser("status")
    manifest_command = commands.add_parser("manifest")
    manifest_command.add_argument("--data-dir", type=Path, default=Path("data/raw/enoe"))
    args = parser.parse_args()

    if args.command == "status":
        print(
            database_sql(
                "SELECT survey_year, survey_quarter, archive_name, content_sha256 "
                "FROM metadata.source_archives ORDER BY survey_year, survey_quarter;"
            ),
            end="",
        )
        return
    if args.command == "manifest":
        print(json.dumps(manifest(args.data_dir), indent=2, sort_keys=True))
        return
    if args.command == "download":
        archive = download(args.period, args.data_dir)
        write_payload(payload(validate_archive(args.period, archive)), None)
        return
    if args.command == "ingest-all":
        results = []
        for year, quarter in CORE_PERIODS:
            period = Period(year, quarter)
            archive = args.data_dir / period.archive_name
            results.append(load(validate_archive(period, archive)))
        print(json.dumps({"periods": results}, indent=2, sort_keys=True))
        return
    if args.command == "audit-all":
        results = []
        for year, quarter in CORE_PERIODS:
            period = Period(year, quarter)
            archive = args.data_dir / period.archive_name
            results.append(staging_audit(validate_archive(period, archive)))
        print(json.dumps({"periods": results}, indent=2, sort_keys=True))
        return
    validated = validate_archive(args.period, _archive_for(args))
    if args.command == "validate":
        write_payload(payload(validated), args.output)
    elif args.command == "ingest":
        print(json.dumps(load(validated), indent=2, sort_keys=True))
    else:
        print(json.dumps(staging_audit(validated), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
