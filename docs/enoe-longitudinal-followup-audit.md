# ENOE longitudinal follow-up audit

Issue #32 adds an aggregate-only diagnostic for possible repeated ENOE
follow-up observations. It is a safeguard against temporal leakage before any
profile fitting; it neither identifies people nor changes the pre-fit model
contract.

## Visit metadata and candidate signature

`SDEM.N_ENT` is retained in `staging.enoe_person_quarter` as interview-visit
metadata. Values 1 through 5 describe the visit position in a sampled dwelling
follow-up cycle. It is a design field, not an ENOE person identifier, a model
feature, or part of the source-table join key.

The diagnostic groups rows under the conservative candidate signature:

```
entity, cd_a, con, v_sel, n_hog, h_mud, n_ren
```

This is a technical follow-up candidate only. It omits nominal information and
is never emitted by the audit. A matching signature may reflect a follow-up
record, but this repository does not claim that it establishes a person's
identity.

## Core staging audit

After applying the migration, reload the 2023 Q1--2025 Q4 official archives so
the new `n_ent` column is populated, then run:

```bash
just db-migrate
just enoe-ingest-all
just enoe-longitudinal-followup-audit
```

The command returns JSON aggregates for every core quarter and every adjacent
quarter transition. It checks visit-value completeness (`1`--`5`), missing or
invalid metadata, ambiguous candidate-signature groups, shared signatures, and
the expected `N_ENT` to `N_ENT + 1` transition. It includes the development to
selection boundary, 2024 Q4 to 2025 Q1.

Existing staged rows predate this migration and have null `n_ent`; their audit
result deliberately reports a reload/review blocker. It does not infer a visit
number from other fields.

## Separate final-evaluation audit

The held-out 2026 files remain outside core staging. With the separately
audited official archives available locally, run:

```bash
just enoe-longitudinal-followup-evaluation-audit
```

This validates the existing 2026 source-integrity decision and calculates only
in-memory aggregates for 2025 Q4 to 2026 Q1 and 2026 Q1 to 2026 Q2. Thus it
reports the selection-to-evaluation boundary without loading 2026, writing
candidate keys, or treating evaluation data as training data.

## Interpretation gate

Both commands always return `candidate_signature_is_approved_linkage: false`
and `leakage_exclusion_approved: false`. The output is evidence for a later
methodological decision, not authorization to exclude observations, randomly
resample, fit a model, or report individual follow-up histories.

Before authorizing a leakage-exclusion rule, review the aggregate transition
rates, signature ambiguity, residence-change implications, and whether the
rule should exclude all cross-role candidate matches or only validated
adjacent-visit transitions. Retain the all-selection estimate as a sensitivity
comparison if a later rule is approved.

## Reviewed aggregate evidence

The local run on 2026-09-30 reloaded the 12 official core archives after the
migration. All 55,546 core candidate records had a valid `N_ENT` value and no
missing or invalid visit metadata. The following boundary diagnostics are
recorded as aggregate evidence only:

| Boundary | Shared signatures | Unambiguous shared signatures | Expected next-visit signatures | Mismatched visits |
|---|---:|---:|---:|---:|
| Development 2024 Q4 to selection 2025 Q1 | 2,686 | 2,656 | 2,654 | 2 |
| Selection 2025 Q4 to evaluation 2026 Q1 | 2,601 | 2,558 | 2,557 | 1 |
| Evaluation 2026 Q1 to 2026 Q2 | 2,552 | 2,484 | 2,483 | 1 |

The 2026 archive-integrity audit passed for separate temporal evaluation. These
counts support reviewing a possible exclusion rule, but do not convert the
signature into a nominal identifier or authorize that rule.
