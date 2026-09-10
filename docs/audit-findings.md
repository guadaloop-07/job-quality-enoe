# Initial source audit — 2026-09-08

The approved window is technically accessible, but Gate A is **not passed**.
Continue semantic and upstream join checks before model preparation.

## Evidence and scope

Source: `postgres-dev`, database `enoe_microdatos`, relation
`public.stg_enoe_microdatos`. Read-only repeatable-read execution captured at
2026-09-08T21:16:59.641277+00:00. The audit covers 188,901 person-quarter rows
and 62,627 candidate person-quarter rows across 14 quarters. These are sample
records, not unique people or pooled population estimates.

Query SHA-256:
`9b196558ded553f325710273e35a9e12c0e54858a8e0cc4a8716c8a9ad9f0323`.
Local evidence: `outputs/source-audit-2026-09-08-v2.json` (excluded from Git).
Reproduce with [the runner](source-audit.md); inspect the output-free
[companion notebook](../notebooks/source_audit.ipynb).

Reviewed local ETL checkout:
`ede43d965c1539d0293763e9e63e4dfbd7e7df4e`, clean when checked.
This identifies the inspected source, not necessarily the code or input archives
that produced the deployed database. Source archive hashes remain unavailable.

## Quarterly profile

All percentages below use the candidate universe. Income-zero percentages and
p3i-NULL percentages use positive quarterly `fac` as their denominator.
Weight sums are diagnostic population totals pending official reconciliation.

| Quarter | Candidate records | Sum of fac | Income zero, weighted % | p3i NULL, weighted % |
|---|---:|---:|---:|---:|
| 2023 Q1 | 4,993 | 2,981,802 | 26.19 | 0.00 |
| 2023 Q2 | 4,664 | 2,975,095 | 27.77 | 0.32 |
| 2023 Q3 | 4,508 | 2,829,876 | 31.43 | 0.44 |
| 2023 Q4 | 4,472 | 2,894,206 | 35.13 | 0.78 |
| 2024 Q1 | 4,346 | 2,871,499 | 31.47 | 0.71 |
| 2024 Q2 | 4,390 | 2,811,270 | 33.96 | 0.89 |
| 2024 Q3 | 4,498 | 2,849,557 | 31.54 | 0.75 |
| 2024 Q4 | 4,558 | 2,882,379 | 38.27 | 0.45 |
| 2025 Q1 | 4,506 | 2,945,254 | 41.69 | 0.17 |
| 2025 Q2 | 4,437 | 2,892,355 | 46.05 | 0.00 |
| 2025 Q3 | 4,398 | 2,786,848 | 46.73 | 8.42 |
| 2025 Q4 | 4,373 | 2,862,420 | 42.69 | 6.69 |
| 2026 Q1 | 4,278 | 2,795,780 | 38.23 | 8.62 |
| 2026 Q2 | 4,206 | 2,763,109 | 40.78 | 8.45 |

## Findings and decisions

- **Technical checks passed, high confidence:** all 14 expected quarters exist;
  no duplicate natural keys or null key components in the audited source window;
  no null/nonpositive factors or null/nonpositive stratum/UPM values among
  candidates. These checks do not establish upstream join correctness or
  statistical representativeness.
- **High analytical risk, high confidence in counts:** `ingocup = 0` represents
  29.86–48.82% of candidate records and 26.19–46.73% of candidate quarterly weight.
  Neither income nor hours contains SQL NULL among candidates. Zero must not
  automatically mean no income, and raw medians must not be interpreted as
  cleaned earnings. Cause is unresolved: verify original codes, derived income
  definitions and ETL transformations before deciding exclusions or imputation.
- **High analytical risk, high confidence in the temporal change:** `p3i` SQL
  NULL grows from at most 0.89% of candidate quarterly weight through 2025 Q2
  to 6.69–8.62% afterward. `tip_con`, `pre_asa`, `seg_soc` and `medica5c`
  have no SQL NULL among candidates, but their special codes remain unverified.
  Check questionnaire applicability and original join matches before attributing
  p3i gaps to nonresponse or substituting variables.
- **High risk for inference, high confidence in observed counts:** distinct
  candidate `est_d_tri` counts shift from 18 through 2024 Q1 to 43–44 in
  2024 Q2–2025 Q1, then 27 from 2025 Q2. This may reflect coding/design changes
  or sample composition; the audit does not establish which. Preserve period
  identifiers and verify the design documentation before pooling strata.
- **High risk for informal-employment benchmarks, high confidence in counts:**
  predicates `tue_ppal = 1` and `emp_ppal = 1` disagree for 23.78–26.57% of
  candidate records by quarter, with neither column NULL. These fields may
  represent different concepts; disagreement alone does not identify the correct
  definition. Resolve semantics before interpreting the existing flag.

Retain 2023–2025 as the core and 2026 Q1–Q2 for additional evaluation.
Do not select a narrower window simply to hide coding or missingness problems.
Next: verify income/hours definitions; map protection and contract codes by
questionnaire; recover an original period to audit joins; investigate design
identifier changes; then decide Gate A. No upstream repair was performed.

## Validation and limitations

The actual aggregate SQL was also executed on synthetic CTE input, without
creating tables, to verify sequential exclusions, missing quarters, invalid
weights, duplicate keys and distinct NULL/zero behavior. No microdata were
exported. Raw categorical code frequencies remain in local evidence.

This is an initial audit, not a harmonized analytical dataset, an official
population reconciliation, a design-valid variance calculation or approval to
fit profiles. No claims about the cause of the observed anomalies are settled.
