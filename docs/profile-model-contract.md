# Profile-model contract

Issue #28 records the decisions that must govern the first model implementation.
It is a **pre-fit contract**: it specifies a descriptive weighted segmentation,
but does not fit, select, serialize, publish, or deploy a model. The
machine-readable source of truth is
[`config/profile_model_contract.json`](../config/profile_model_contract.json).
Run `just profile-model-contract-validate` to fail closed if that contract is
changed outside its approved scope.

## Purpose and supported interpretation

The model may identify interpretable, stable patterns of employment conditions
among the approved ENOE person-quarter universe. It is not an individual
prediction, a worker ranking, a causal estimate, a universal job-quality score,
or an official INEGI category. Jalisco statewide is the sole supported domain;
municipal estimates and profiles remain out of scope.

The fit input is `analysis.enoe_person_quarter_prepared`, at one person-quarter
per row. `analysis.enoe_weighted_profile` and
`analysis.enoe_weighted_profile_labeled` are aggregate descriptive outputs and
must never be used as training input.

## Input contract

The fit has five categorical dimensions. Each encoder must retain the response
state as part of the category; it must not turn an unknown, missing, or
not-applicable response into a substantive employment condition.

| Dimension | Prepared input | Treatment |
|---|---|---|
| Income band | `income_band`, `income_band_state` | Preserve observed bands, no income, unspecified, and missing. Exact nominal income is excluded. |
| Working-time duration | `dur9c` | Preserve temporary absence, duration bands, unspecified, and missing. Do not use stored zero hours as zero work. |
| Employment health access | `has_health_access`, `health_access_state` | Preserve with/without access, unspecified, and missing. |
| Non-health benefits | `has_other_benefits`, `other_benefits_state` | Preserve with/without benefits, unspecified, and missing. |
| Contract status | `has_written_contract`, `contract_type`, `contract_type_state` | Encode temporary, indefinite, type-unspecified, no written contract, unspecified, and missing as one dimension. |

`EMP_PPAL` and `TUE_PPAL` are descriptive-only until their distinct semantics
are resolved; neither may define or benchmark a fitted segment. `RAMA`,
`C_OCU11C`, and `EMPLE7C` may describe a fitted segment but are not fit inputs.
`MEDICA5C` is a consistency check, not a third protection dimension; `P3I` is
questionnaire-specific and excluded across quarters. See the
[variable dictionary](variable-dictionary.md) for their source rules.

No substantive imputation is allowed. A future fitting run must also compare
its selected solution with a complete-response sensitivity subset and report if
the solution is materially driven by response states.

## Time, weights, and dependence

| Role | Periods | Rule |
|---|---|---|
| Development | 2023 Q1–2024 Q4 | Estimate candidate solutions only. |
| Temporal selection | 2025 Q1–Q4 | Choose among predeclared candidates; do not use it for initial feature decisions. |
| Held-out temporal evaluation | 2026 Q1–Q2 | Evaluate only after specification freeze; keep separate from training, selection, staging, and the descriptive baseline. |

The 2026 archive audit supports this separate evaluation role, not pooling or
training on 2026. Its COE-derived changes remain subject to the documented
[temporal-evaluation limit](enoe-2026-temporal-evaluation.md).

Eligible records have `analysis_weight > 0`. The fit must use
`analysis_weight` normalized to sum to one within each survey quarter, giving
each quarter equal influence without treating pooled person-quarters as a
population total. Within-quarter descriptive estimates continue to use the
original weights.

Non-temporal random resampling is prohibited until a repeat-observation audit
documents a defensible linkage rule. Selection is quarter-based, and any future
temporal interpretation requires an overlap audit for repeat observations.

## Candidate family and acceptance gates

The initial candidate family is weighted latent class analysis on the five
categorical dimensions, with 2–6 candidate profile counts. A future fitting
issue must implement multi-start convergence checks and may select a solution
only in this order:

1. Convergence and no invalid encoded categories.
2. Temporal stability, at least 0.80 under the documented stability statistic.
3. Each selected profile has at least a 5% weighted share.
4. Information criterion among the surviving candidates.
5. Plain-language interpretability without defining a profile by missingness
   alone.

The fitting issue must name the exact stability statistic, label-alignment
method, multi-start protocol, and tolerance before it executes. Those choices
are implementation details constrained by this contract, not invitations to
relax its gates after seeing results.

## Reproducibility and disclosure

Each future run must record the contract SHA-256, source archive SHA-256 values,
Git commit, random seed, and period role. Microdata and model binaries remain
outside Git. Any published fitted-profile category estimate follows the current
minimum of 30 unweighted records and requires INEGI disclosure review.

The contract prohibits individual prediction or ranking, causal claims,
municipal profiles, 2026 training, and public deployment. A later issue must
explicitly authorize fitting after it implements these gates and reviews the
resulting evidence.
