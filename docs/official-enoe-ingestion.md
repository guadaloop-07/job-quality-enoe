# Official ENOE ingestion

Issue #8 loads the repository-owned database directly from official INEGI ENOE
CSV archives. It never reads `postgres-dev`, `iieg_postgres`, ETL-SIEEJ, or a
database dump. Archives are stored under `data/raw/enoe/`, which Git ignores.

## Prerequisites

Start the independent database and apply all migrations:

```bash
just db-up
just db-migrate
```

The ingestion scope is the 12 quarters from 2023 Q1 through 2025 Q4, for the
provisional Jalisco candidate universe: complete interview, accepted residency,
age 15--98, occupied, and `POS_OCU = 1`.

## Download and validate one period

Download an archive directly from INEGI:

```bash
just enoe-download 2023Q1
```

The command writes the archive to `data/raw/enoe/` and prints only aggregate
provenance and validation results. Validate an already downloaded archive
without connecting to PostgreSQL:

```bash
just enoe-validate 2023Q1 data/raw/enoe/enoe_2023_trim1_csv.zip
```

Validation requires exactly one SDEM, COE1, and COE2 CSV; exactly one of `ENT`
or `CVE_ENT` in each source; the complete official resident key; unique keys;
and one-to-one COE matches for every candidate. It rejects failures before any
database transaction begins. Output contains only archive metadata and
aggregates, never survey rows or resident keys.

## Load and reconcile

Load a validated period transactionally:

```bash
just enoe-ingest 2023Q1 data/raw/enoe/enoe_2023_trim1_csv.zip
just enoe-audit 2023Q1 data/raw/enoe/enoe_2023_trim1_csv.zip
```

The load replaces only that period after all source checks complete. It stores
the official key `TIPO, MES_CAL, CD_A, entity, CON, V_SEL, N_HOG, H_MUD, N_REN`,
raw source codes required by the variable dictionary, archive hash/URL/size,
retrieval time, and ingestion revision. It verifies candidate row count and
positive weight total before committing. Repeating a validated load is
deterministic; no loading operation uses `ON CONFLICT DO NOTHING`.

After all archives are downloaded, load the full window and inspect the source
metadata:

```bash
just enoe-ingest-all
just enoe-audit-all
just enoe-status
just enoe-manifest
```

Run `just enoe-audit` for one period or `just enoe-audit-all` for the full
window, and retain generated aggregate results outside Git with the downloaded
archives. Do not commit archives, database exports, generated audits,
credentials, or any microdata-derived output.

The committed [official source manifest](official-enoe-source-manifest.md)
records the URL pattern, byte sizes, and SHA-256 values for the approved core
window without including data rows.
