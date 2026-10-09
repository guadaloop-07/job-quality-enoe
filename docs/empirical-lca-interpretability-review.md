# Empirical LCA interpretability review

Issue #41 pre-specifies the human review required after the first guarded
candidate dossier and before any fixed-solution robustness analysis. It does
not authorize fitting, scoring, publication, deployment, 2026 training, or a
change to the profile-model contract.

## Decision boundary

The candidate dossier is the only source for this review. It contains aggregate
conditional response probabilities and gate diagnostics, but no identifiers,
microdata, individual assignments, or persisted model artifact. The review may
consider only the information-criterion winner reported by that dossier. It may
not select a different profile count, relax a failed gate, add a fit feature,
or change the temporal split.

The ordered gates remain those in the
[profile-model contract](profile-model-contract.md): convergence and valid
encoded inputs; temporal stability of at least 0.80; minimum weighted profile
share of 5%; Kish-rescaled survey pseudo-BIC; then interpretability. If no
candidate passes the pre-interpretability gates, there is no selection. If the
information-criterion winner is not interpretable under this protocol, there
is no fixed-solution robustness run; record the decision and open a separately
scoped issue before considering any future methodological change.

## Review procedure

Two reviewers with relevant labour-market expertise independently inspect the
aggregate dossier. They first record whether the candidate is interpretable,
then reconcile any disagreement in a short joint note. A disagreement that
cannot be reconciled is a decision not to select a solution. Reviewers must not
inspect individual-level data or create a new model comparison during review.

For every proposed profile label, the joint note must establish all of the
following:

1. A plain-language label that describes an employment-conditions pattern, not
   a person type or an official INEGI category.
2. At least two distinct substantive dimensions supporting the label, selected
   from income band, working-time duration, employment health access,
   non-health benefits, and contract status.
3. Evidence from the aggregate conditional response probabilities for each
   cited dimension.
4. Confirmation that the label is not defined only by missing, unspecified, or
   other response-quality states.
5. A statement that the result is descriptive, statewide for Jalisco, and not
   a causal, municipal, predictive, or official-category claim.

The review must reject labels that merely restate a response-quality state, use
normative language unsupported by the five dimensions, or imply that members
of a profile are homogeneous people rather than observations with estimated
probabilistic patterns.

## Local review record

Store the review record alongside the aggregate dossier written by
`just profile-lca-candidate-dossier <output-path>` in a secure, non-versioned
location. Do not commit either file to Git. The record supplied to
`profile-lca-fixed-robustness` must contain the required fields:

```json
{
  "selected_k": 0,
  "plain_language_label": "pending review",
  "substantive_dimensions": ["income_band", "contract_status"],
  "not_defined_by_response_states_alone": true
}
```

The example is a schema illustration, not an approved result. The actual local
record should also preserve the dossier timestamp, contract hash, source
archive hashes, code commit, random seed, reviewer roles, agreement outcome,
and a concise label rationale. These additional fields are provenance for the
review and do not alter the model-selection rule.

## Next permitted action

Only after an interpretable selection is documented may the fixed-solution
robustness command run for that same `selected_k`. The 2026 archives remain
held out until the specification is frozen and may be used once for final
evaluation only.
