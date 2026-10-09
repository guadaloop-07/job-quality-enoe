# Final held-out 2026 evaluation

Issue #50 authorizes one guarded, aggregate-only evaluation of the reviewed
three-pattern (`K=3`) employment-conditions solution in the official 2026 Q1
and Q2 ENOE archives. It does not authorize a new candidate search, a changed
label, training on 2026, pooling 2026 with the core window, individual scoring,
or a persisted model artifact.

## Frozen specification and estimands

The runner revalidates the 2026 archive-integrity decision, encodes only the
five contract-approved dimensions in memory, and quarter-normalizes
`analysis_weight`. It refits the predeclared `K=3` reference only on the
2023 Q1--2024 Q4 development window with the fixed 32-start protocol. The
2025 selection window is used only to retain the categorical support already
fixed by the reviewed dossier; neither 2025 nor 2026 can change the solution.

Each 2026 quarter is then scored against that frozen development reference;
the runner does not fit a model to evaluation rows. Its disclosure-safe output
contains only the quarter-normalized mean log likelihood, posterior-weighted
profile shares, disclosure-eligible aggregate MAP profile counts, and run
provenance. It emits no source rows, identifiers, individual probabilities,
assignments, or model parameters.

The existing local interpretability record is required. It must select `K=3`
and contain one reviewed plain-language label for each frozen profile. Every
aggregate profile count must satisfy the existing minimum of 30 unweighted
records; otherwise the runner fails without returning profile estimates.

## Run

Run only after the specification is frozen and the official 2026 archives are
available locally:

```bash
just enoe-prepare
just profile-fitting-input-audit
just profile-longitudinal-sensitivity-audit
just enoe-evaluation-audit
just profile-lca-final-held-out-evaluation /secure/path/interpretability-review.json
```

Keep the resulting aggregate evidence outside Git. The archive audit remains
the sole authorization for the source inputs and does not put 2026 in staging.
