# Weighted official-classifier profile protocol

Issue #17 defines a reproducible descriptive protocol for the repository-owned
ENOE path. It is not a latent segmentation, score, predictive model, or an
INEGI category. The only publication interface is the aggregate view
`analysis.enoe_weighted_profile` through `just enoe-profile`.

## Scope, universe, and supported domain

The unit is a person-quarter. Each estimate is calculated separately for each
quarter from 2023 Q1 through 2025 Q4. The universe is Jalisco residents in the
prepared view: `entity = 14`, complete interview (`r_def = '0'`), accepted
residence (`c_res IN ('1', '3')`), age 15--98, occupied (`clase2 = '1'`), and
subordinate and paid (`pos_ocu = '1'`). The profile therefore records position
in occupation as an official classifier, but has only its universe-supported
category in this release.

Jalisco statewide is the only supported publication domain. The records retain
municipal identifiers only where official confidentiality rules allow them, but
this does not establish municipal representativeness. No municipal profile is
published. The 2026 window is excluded.

`FAC_TRI`, retained as `analysis_weight`, is the quarterly expansion factor. A
cell is eligible only when `analysis_weight > 0`. For every quarter and
classifier, the denominator is the sum of eligible weights over the full
universe for that quarter, including valid, unspecified, not-applicable, and
missing response states. Person-quarters must not be pooled into a population
estimate across quarters.

## Classifiers and source versions

The controlling source is INEGI, *Encuesta Nacional de Ocupación y Empleo
(ENOE). Estructura de la base de datos. Segunda edición. 2025*, SDEMT fields
58--65 and 107--108. It is recorded in the versioned database catalog. The
2025 structure is used provisionally for the 2023--2024 archives; source
structure must be rechecked before publication if INEGI issues a period-specific
change.

| Published classifier | Field and valid treatment |
|---|---|
| Position in occupation | `POS_OCU`: 1--4 valid; 5 unspecified. The universe keeps code 1 only. |
| Employment formality | `EMP_PPAL`: 1 informal employment; 2 formal employment. |
| Informal sector | `TUE_PPAL`: 1 informal sector; 2 outside the informal sector. It is never used as a synonym for `EMP_PPAL`. |
| Activity branch | `RAMA`: 6 agricultural, 1 construction, 2 manufacturing, 3 commerce, 4 services, 5 other; 7 unspecified. |
| Occupation | `C_OCU11C`: 1--10 official occupation groups; 11 unspecified. |
| Income band | `ING7C`: 1--5 income bands and 6 no income are valid; 7 unspecified. Exact income remains a separate preparation field. |
| Working-time duration | `DUR9C`: 1 temporary absence with a work link; 2--8 duration bands; 9 unspecified. |
| Unit size | `EMPLE7C`: 1 one person; 2 2--5; 3 6--10; 4 11--15; 5 16--50; 6 51+; 7 unspecified. |
| Written contract | Governed `TIP_CON` preparation: with written contract, without written contract, unspecified, or missing. |
| Contract type | Governed `contract_type_state`: observed type, type unspecified, not applicable when there is no written contract, unspecified, or missing. |
| Employment-based health access | Governed `SEG_SOC` preparation: with access, without access, unspecified, or missing. |
| Non-health benefits | Governed `PRE_ASA` preparation: with benefits, without benefits, unspecified, or missing. |

`RAMA`, `C_OCU11C`, and `EMPLE7C` are retained during ingestion alongside the
previously retained `EMP_PPAL` and `TUE_PPAL`. After applying migration 0005,
reload each core archive before treating those three fields as observed.

## Missingness and disclosure

The output never folds a response state into a substantive category. SQL keeps
`valid`, `unspecified`, `not_applicable`, and `missing` as distinct
`category_state` values; invalid codes fail the profile guardrail. In particular,
no contract is an absence of written contract, while its contract *type* is not
applicable. A `NULL` source value is missing, not unspecified.

`just enoe-profile` returns aggregate evidence only. It validates that the core
window is complete, weights are positive, official codes are valid, category
cells reproduce their quarterly unweighted and weighted denominators, and shares
match their weighted cells and sum to one within a `1e-12` decimal tolerance.
The tolerance admits only database-division rounding, not a changed weighted
denominator. Before emitting a result it suppresses all estimates for cells with
fewer than 30 unweighted person-quarters. A suppressed record retains only its
period, classifier, category code, category state, and suppression flag; it does
not expose a count, weight, denominator, or share. This is a minimum disclosure
control, not a release authorization; apply INEGI disclosure review before any
external publication.

## Runbook

```bash
just db-migrate
just enoe-ingest-all
just enoe-prepare
just catalog-validate
just enoe-profile
```

Do not commit command output, archives, database volumes, or microdata. The
catalog describes every source classifier and aggregate-output column; inspect
it with the queries in [the database catalog guide](database-catalog.md).
