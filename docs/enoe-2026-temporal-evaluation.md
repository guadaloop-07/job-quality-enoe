# ENOE 2026 temporal-evaluation audit

Issue #22 audits official ENOE 2026 Q1--Q2 archives against the 2025 Q4
reference archive. It is a source-integrity and schema-comparability gate for
separate temporal evaluation only; it does not load 2026 data into staging or
extend the approved 2023 Q1--2025 Q4 core profile and baseline window.

## Decision recorded on 2026-09-24

The source-integrity gate passed for a **separate** temporal evaluation of the
approved profile classifiers. This decision does not extend the core period;
the 2026 archives remain outside the staging database and descriptive baseline.

| Period | Archive bytes | SHA-256 | Candidate records | Positive expansion weight | Unmatched COE1 / COE2 |
| --- | ---: | --- | ---: | ---: | --- |
| 2026Q1 | 40,843,186 | `934a1b403d839c9bc777f40ef39f7d0a5b2b43c9852b748b4cd7165bf0f41666` | 4,387 | 2,831,831 | 0 / 0 |
| 2026Q2 | 35,213,597 | `020811fa989a3e4e3e0daae39b32df6bb055f3ca59653b76ecc454f9b231d91e` | 4,355 | 2,808,513 | 0 / 0 |

Both periods had complete coverage for the 16 raw fields used by the approved
profile protocol and zero invalid values in its governed categorical codes.
The normalized SDEM header was unchanged from 2025Q4 in both periods. All
normalized headers were unchanged in 2026Q2. In 2026Q1, COE1 and COE2 contain
changes outside the profile protocol; their required key fields, including
COE1 `p3i`, remain available. Consequently, 2026Q1 must not support an
extension to any COE-derived analysis without a separate questionnaire review.

The archive names and release availability are recorded by the official
[INEGI ENOE documentation](https://www.inegi.org.mx/programas/enoe/).

## Checks

For each 2026 archive, the audit requires the official SDEM--COE1--COE2 key,
one-to-one COE matches for the Jalisco candidate universe, positive `FAC_TRI`,
and required source fields. It reports aggregate source and candidate counts,
positive weights, non-null coverage of every source field used by the profile,
and invalid-code counts for governed classifiers.

The audit normalizes `ENT` and `CVE_ENT` as the same entity field before
comparing each SDEM, COE1, and COE2 header to 2025 Q4. It reports added and
removed fields but fails closed when a required field is missing, no candidate
value is available for a profile source field, a governed code is invalid, or a
source join or weight check fails.

## Runbook

Download only the evaluation candidates, then audit them with the local 2025 Q4
reference archive:

```bash
just enoe-evaluation-download 2026Q1
just enoe-evaluation-download 2026Q2
just enoe-evaluation-audit
```

The commands emit aggregate provenance and evidence only. Keep archives and
generated audit output outside Git. A passing source-integrity decision permits
separate temporal-evaluation planning; it does not authorize pooling 2026 with
the core window, adding it to the profile baseline, or model fitting.
