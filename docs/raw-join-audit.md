# Raw SDEM–COE join audit

The official source files are joinable, but the current deployed staging table
is not safe for modeling. This audit uses aggregate diagnostics only and never
emits a person, household, or source row.

## Required key

INEGI's *Encuesta Nacional de Ocupación y Empleo (ENOE). Estructura de la base
de datos. 2025* defines the resident key shared by SDEM, COE1, and COE2 as:

    TIPO, MES_CAL, CD_A, ENT/CVE_ENT, CON, V_SEL, N_HOG, H_MUD, N_REN

ENT applies through 2025 Q2 and CVE_ENT from 2025 Q3. The audit canonicalizes
that alias and requires every key column. It fails closed when the official key
is incomplete, duplicated, unmatched, or produces more than one COE match.

The inspected ETL instead uses CD_A, ENT, CON, V_SEL, N_HOG, H_MUD, N_ENT,
N_REN, taking only the intersection of available fields. It omits TIPO and
MES_CAL; from 2025 Q3 it also omits the entity because COE extraction does not
retain CVE_ENT. Loading uses the same nonofficial storage key with
ON CONFLICT DO NOTHING, so collisions are silently discarded.

## Reproduce

Download official archives to a temporary directory outside the repository,
then run:

    uv run --locked python scripts/audit_raw_joins.py \
      --source 2023Q1=/tmp/enoe/enoe_2023_trim1_csv.zip \
      --source 2025Q2=/tmp/enoe/enoe_2025_trim2_csv.zip \
      --source 2025Q3=/tmp/enoe/enoe_2025_trim3_csv.zip \
      --output outputs/raw-join-audit.json

The output path is ignored by Git and opened exclusively. The payload contains
archive hashes, row counts, weights, duplicate/unmatched totals, and current-key
diagnostics—not raw records or key values.

## Reviewed evidence

Captured 2026-09-10 from the official archives. All three official joins are
one-to-one and complete for the provisional Jalisco candidate universe.

| Period | Raw candidates | Official join | Storage-key excess rows | Current COE1 multiple matches | First COE1 match from another entity | First COE1 match has blank p3i |
|---|---:|---|---:|---:|---:|---:|
| 2023 Q1 | 5,085 | Safe | 35 | 173 | 0 | 53 |
| 2025 Q2 | 4,437 | Safe | 0 | 0 | 0 | 0 |
| 2025 Q3 | 4,460 | Safe | 24 | 622 | 338 | 268 |

For 2025 Q3, the first wrong-entity COE1 match represents 348,589 in candidate
weight; the first blank-p3i match represents 247,868. COE2 has 622 multiple
matches and 318 first matches from another entity. “First match” reproduces the
source-file order relevant to the current left merge and conflict handling; it
is diagnostic evidence, not a repaired record-level result.

Official archive provenance:

| Period | Bytes | SHA-256 |
|---|---:|---|
| 2023 Q1 | 37,487,716 | ae627ebd3b749f15b5faf27fdc59dadb69a696a5f359d1faa7aae5eae856041c |
| 2025 Q2 | 38,752,236 | 291db61afcc472a0933d2bebf46720cfd024df8912dc899d541d8109bd406722 |
| 2025 Q3 | 40,062,680 | d2817a14201694e119a3fd6fcb8b8ed7619ea7e26cf8b353761a1ac1f23d6022 |

Source URLs are recorded in the generated payload and follow INEGI's official
enoe_<year>_trim<quarter>_csv.zip publication path.

## Required upstream remediation

1. Canonicalize ENT/CVE_ENT before selecting columns in every source table.
2. Require the complete official key; never join on the intersection of columns.
3. Use a one-to-one merge validation and record explicit COE1/COE2 match flags.
4. Include TIPO and MES_CAL in the stored uniqueness constraint; do not use
   N_ENT as a substitute for those fields.
5. Fail the load on duplicate source keys instead of silently discarding them.
6. Reload and verify 2023 Q1–2026 Q2 before building the analytical dataset.

The permanent repair belongs in the ETL repository. A local analytical
transformation cannot recover records already discarded or identify the correct
COE row after an unsafe merge.
