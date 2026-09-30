# Guarded weighted latent-class engine

Issue #36 implements a reproducible weighted categorical latent-class analysis
(LCA) engine. It is intentionally **synthetic-only**: it has no database query,
file reader for ENOE microdata, model serializer, or command that can fit ENOE.
The profile-model contract remains `contract_only` and
`model_artifacts_allowed: false`.

## Approved computational protocol

The engine accepts only an in-memory sequence of rows with exactly two fields:
`tokens` (the five approved categorical dimensions) and a positive `weight`.
It rejects identifiers, periods, source values, descriptive fields, and any
extra field. Thus it cannot silently expand the model input beyond the encoder
guardrails in [profile fitting inputs](profile-fitting-inputs.md).

For each candidate count from 2 through 6, the specified procedure is:

1. Run weighted categorical EM from 32 starts, using
   `base_seed + start_index` for start indices 0–31.
2. Update class probabilities and one conditional response distribution per
   approved dimension using supplied weights. A probability floor of `1e-12`
   avoids logarithms of zero.
3. Stop a start when the relative log-likelihood change is at most `1e-8`, or
   report it unconverged after 500 iterations. Only converged starts are
   eligible; the highest log likelihood is retained.

This protocol is fixed in
[`config/profile_model_contract.json`](../config/profile_model_contract.json)
and its validator fails if those values change.

## Stability and selection gates

Class labels have no intrinsic order. To compare two fits with the same number
of classes and category definitions, the engine evaluates all permutations of
class labels. It chooses the alignment with the smallest mean total-variation
distance across the five conditional distributions and reports stability as
one minus that distance.

`select_candidate` applies the predeclared gates in this exact order:
convergence; stability at least 0.80; every weighted class share at least 5%;
lowest information criterion among survivors; then human interpretability. It
does not invent a tie-breaker, and it refuses an uninterpretable
information-criterion winner rather than selecting a different candidate after
inspection. Its output still says `fit_authorized: false`.

Before a later reporting layer may publish a fitted-profile estimate, the engine
also applies the contract's disclosure guard: every profile must have at least
30 unweighted records. A smaller cell is not made publishable by a large survey
weight.

## Verification boundary

Run the deterministic synthetic-only check with:

```bash
just profile-lca-synthetic-check
```

It uses two deliberately separable, fictional response patterns and emits only
aggregate algorithm diagnostics. Passing this check demonstrates code behavior,
not an ENOE result or authorization to train. A later review must explicitly
authorize the data interface, run metadata, fitting evidence, and a contract
status change before any ENOE fit can occur.
