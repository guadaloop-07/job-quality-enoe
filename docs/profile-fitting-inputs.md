# Profile fitting inputs and temporal safeguards

Issue #30 implements the guarded inputs required by the
[profile-model contract](profile-model-contract.md). It does **not** fit,
serialize, select, publish, or deploy a model. The contract remains
`contract_only`; every command in this document returns aggregate audit evidence
only.

## Deterministic input encoding

`scripts/profile_fitting_inputs.py` accepts only the five source groups approved
by the contract, plus survey-period and weight metadata. It rejects every extra
field, including `EMP_PPAL`, `TUE_PPAL`, `P3I`, exact income, descriptive
classifiers, and aggregate profile views. This makes the feature role explicit
rather than relying on a caller to omit fields correctly.

| Dimension | Token groups | Unsafe combinations rejected |
|---|---|---|
| Income band | `income_band_1`–`income_band_5`, `no_income`, `unspecified`, `missing` | A band that conflicts with `income_band_state` |
| Working-time duration | `temporary_absence`, `duration_2`–`duration_8`, `unspecified`, `missing` | Any non-governed `DUR9C` value |
| Employment health access | `with_access`, `without_access`, `unspecified`, `missing` | A boolean that conflicts with `health_access_state` |
| Non-health benefits | `with_benefits`, `without_benefits`, `unspecified`, `missing` | A boolean that conflicts with `other_benefits_state` |
| Contract status | `temporary`, `indefinite`, `type_unspecified`, `without_written_contract`, `unspecified`, `missing` | Inconsistent written-contract, type, and response-state fields |

The encoder keeps nonresponse, missingness, and contract non-applicability out
of substantive categories. It retains one local person-quarter input row for a
future fitter but never writes those rows, raw identifiers, or model artifacts.

## Core input audit

Run the aggregate-only audit after the preparation guardrail:

```bash
just enoe-prepare
just profile-fitting-input-audit
```

The audit requires every development (2023 Q1–2024 Q4) and selection (2025
Q1–Q4) period, a positive `analysis_weight`, and zero invalid encodings. It
normalizes weights to sum to one inside each survey quarter for a future fit;
the original weights remain the only weights for within-quarter descriptive
estimates. It does not materialize an input dataset or fit a candidate.

## Repeat-observation safeguard

The audit reports overlap between development and selection under the candidate
signature `entity, cd_a, con, v_sel, n_hog, h_mud, n_ren`. It intentionally
labels this as an **unapproved candidate signature**, not a longitudinal person
identifier: its stability across ENOE rotations has not been demonstrated.

Therefore, no non-temporal random split, bootstrap, or resampling is permitted.
The approved selection design remains a quarter-based temporal holdout. A later
fitting implementation must perform and document a linkage/overlap audit before
interpreting temporal results.

## Held-out 2026 interface

The separate evaluation interface accepts only 2026 Q1 and Q2 archives that
pass the existing official archive audit:

```bash
just enoe-evaluation-audit
just profile-fitting-evaluation-audit
```

It consumes the audit decision and returns only period-level provenance and
candidate counts. It does not load 2026 into staging, add it to development or
selection, or authorize model fitting. See the
[2026 temporal-evaluation audit](enoe-2026-temporal-evaluation.md) for its
questionnaire-comparability limit.

## Remaining authorization gate

The next issue may implement the weighted latent-class optimizer only after it
names the stability statistic, label-alignment method, multi-start protocol, and
convergence tolerance. It must then present the resulting evidence for review
before changing the model contract to allow a fit.
