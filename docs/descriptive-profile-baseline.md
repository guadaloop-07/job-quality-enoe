# Descriptive ENOE profile baseline

Issue #20 provides a reproducible, aggregate-only Markdown baseline from the
repository-owned ENOE profile view. It is a descriptive companion to the
[weighted official-classifier protocol](weighted-profile-protocol.md), not a
latent segmentation, score, predictive model, or official INEGI category.

## Scope

The command covers the complete core window, 2023 Q1 through 2025 Q4, for the
prepared Jalisco statewide universe. It uses the quarterly `FAC_TRI` expansion
factor retained as `analysis_weight`; every quarter is estimated separately.
The command never pools person-quarters into a multi-quarter population
estimate, makes municipal claims, or extends the window to 2026.

The baseline presents the largest disclosure-eligible weighted category in each
quarter for every classifier in the protocol. Employment formality (`EMP_PPAL`)
and informal sector (`TUE_PPAL`) are shown as separate classifiers. A leading
category is a descriptive summary only; it is not a profile assignment or a
ranking of employment quality.

## Run the report

After the profile prerequisites have passed, render the report to standard
output or redirect it outside the repository:

```bash
just enoe-baseline
just enoe-baseline > /tmp/enoe-descriptive-profile-baseline.md
```

The command calls `just enoe-profile`'s guarded reporting layer. It fails closed
when the core period set is incomplete, the classifier set differs from the
approved protocol, or no disclosure-eligible category is available for a
classifier-quarter. Suppressed cells never expose a count, weight, denominator,
or share in the baseline.

Do not commit rendered output, database exports, archives, or microdata. The
versioned command, tests, and this documentation define the reproducible
artifact; its values are refreshed from the local official staging database.
