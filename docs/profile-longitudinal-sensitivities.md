# Profile longitudinal sensitivities

Issue #34 implements the approved temporal-dependence policy as a pre-fit,
aggregate-only guardrail. It does not fit ENOE data, identify people, export
candidate signatures, materialize model inputs, or permit non-temporal
resampling.

## Fixed hierarchy

The same person-quarter universe and quarterly weights are used in all three
analyses. Only the eligibility of target-role observations changes.

| Analysis | Eligibility rule | Permitted use |
|---|---|---|
| Primary | In selection, remove every signature anchored by an unambiguous 2024 Q4 to 2025 Q1 transition with `N_ENT + 1`; in evaluation, analogously remove signatures anchored by 2025 Q4 to 2026 Q1. The removal applies to that signature's target-role observations. | Candidate-model selection and primary temporal interpretation. |
| Sensitivity A | Keep the complete temporal target-role universe. | Fixed-solution robustness only. |
| Sensitivity B | Remove every target-role candidate signature that appears in any prior role, regardless of its visit transition. | Fixed-solution conservative robustness bound only. |

The primary rule relies on a technical follow-up candidate, not nominal person
linkage. It requires one record per signature in both adjacent quarters and an
increment from a valid visit number 1--4 to the next visit. Missing, invalid, or
ambiguous visit metadata cannot anchor a primary exclusion. Sensitivity B can
overexclude; it is intentionally not an identity claim.

The primary analysis alone may select the number of profiles. Sensitivities A
and B must use the frozen solution and report profile size, encoded-dimension
composition, and aligned-profile stability; they may not change model count,
features, thresholds, or labels after results are observed.

## Reproduce

After downloading the governed official archives through 2026 Q2, run:

```bash
just profile-longitudinal-sensitivity-audit
```

The command validates the model contract and the existing 2026 source-integrity
gate, reads official archives only in memory, and returns per-period,
per-analysis record and positive-weight accounting. It never writes raw rows,
candidate signatures, a split file, or a fitted artifact. 2026 remains outside
staging and fitting.

The audit fails if an expected period is absent, an input weight is not positive,
or `N_ENT` is missing or outside 1--5. It also verifies that eligible plus
excluded records and weights reconcile to each period's input totals.

## Interpretation

Agreement among the primary result and both sensitivities supports robustness to
plausible repeat follow-up. Divergence is evidence that temporal dependence may
materially affect the segmentation; it blocks publication or deployment rather
than selecting the most favorable result.
