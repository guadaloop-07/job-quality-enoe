# First guarded empirical LCA fit

Issue #38 authorizes a narrow first ENOE fit. It does not authorize individual
scores, deployment, municipal estimates, 2026 training, raw-data export, model
binaries, or committing any result to Git.

## Preflight and data boundary

Run the candidate dossier only after the current database and official archive
checks pass:

```bash
just enoe-prepare
just profile-fitting-input-audit
just profile-longitudinal-sensitivity-audit
just enoe-evaluation-audit
just profile-lca-candidate-dossier outputs/candidate-dossier-YYYY-MM-DD.json
```

The runner reads `analysis.enoe_person_quarter_prepared` in read-only mode. SQL
uses candidate signatures and `N_ENT` only inside the database to apply the
approved primary exclusion at the 2024 Q4--2025 Q1 boundary. Its final
projection contains only survey period, the five approved source groups, and
`analysis_weight`; the in-memory fitter receives only encoded tokens and a
within-quarter-normalized weight. Neither signatures nor raw identifiers are
included in the output.

The command also confirms the official 2026 archives before fitting, but does
not read them as training or selection rows. They remain held out until a
specification is frozen.

## Candidate dossier

The primary analysis fits K=2--6 with the fixed weighted categorical EM
protocol. It fits a pooled development reference (2023 Q1--2024 Q4) and each
primary selection quarter independently (2025 Q1--Q4). A candidate's temporal
stability is the **minimum** label-aligned stability between that reference and
each selection-quarter fit; it must be at least 0.80.

For the information-criterion gate, each selection-quarter weighted log
likelihood is scaled by that quarter's Kish effective sample size before the
BIC penalty. The four resulting values are summed. This predeclared
Kish-rescaled survey pseudo-BIC avoids letting a one-unit normalized survey
weight distort the standard BIC penalty while retaining equal quarter influence.

The dossier reports convergence, per-quarter stability, minimum weighted share,
pseudo-BIC, reproducibility metadata, and aggregate conditional response
probabilities for review. It does not automatically select a profile count:
the pseudo-BIC winner remains pending a documented interpretability decision.
That decision must follow the [empirical LCA interpretability review
protocol](empirical-lca-interpretability-review.md), including a plain-language
label supported by at least two substantive dimensions. Missing, unspecified,
and response-quality states alone cannot define a profile.

The output path is required. It is created exclusively, so it cannot replace
earlier evidence, and `outputs/` is excluded from Git. Store the aggregate
dossier and its subsequent interpretability review record together in a secure
local location. The payload contains no source rows, identifiers, individual
scores, or model parameters.

After that review, the chosen K is fixed. Complete-response, sensitivity A, and
sensitivity B analyses may assess that fixed solution only; they cannot choose
another K. Run them by supplying a local, non-versioned JSON review record with
`selected_k`, `plain_language_label`, at least two `substantive_dimensions`,
and `not_defined_by_response_states_alone: true`:

```bash
just profile-lca-fixed-robustness /secure/path/interpretability-review.json
```

The 2026 archives may then be used once for final evaluation only, using the
[final held-out 2026 evaluation](final-held-out-2026-evaluation.md) protocol.
