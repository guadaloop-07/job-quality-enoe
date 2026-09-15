# Independent ENOE staging reconciliation

Captured on 2026-09-11 from the official archives listed in the
[source manifest](official-enoe-source-manifest.md), using the independent
PostgreSQL environment. The audit compares only aggregate candidate counts and
positive survey-weight totals; it does not emit source rows or resident keys.

| Period | Raw candidates | Positive survey weight | Reconciled with staging |
|---|---:|---:|---|
| 2023 Q1 | 5,085 | 3,010,546 | Yes |
| 2023 Q2 | 4,775 | 3,013,277 | Yes |
| 2023 Q3 | 4,676 | 2,899,196 | Yes |
| 2023 Q4 | 4,647 | 2,968,362 | Yes |
| 2024 Q1 | 4,579 | 2,968,971 | Yes |
| 2024 Q2 | 4,594 | 2,908,511 | Yes |
| 2024 Q3 | 4,646 | 2,922,149 | Yes |
| 2024 Q4 | 4,648 | 2,923,184 | Yes |
| 2025 Q1 | 4,546 | 2,962,647 | Yes |
| 2025 Q2 | 4,437 | 2,892,355 | Yes |
| 2025 Q3 | 4,460 | 2,815,242 | Yes |
| 2025 Q4 | 4,453 | 2,890,224 | Yes |

Every period passed the full-key source validation before loading: one SDEM,
COE1, and COE2 CSV; canonical `ENT`/`CVE_ENT`; complete unique official keys;
and complete one-to-one COE matches for the candidate universe. Repeating a
validated period load replaces only that period transactionally.

This evidence applies to the independent project database only. It does not
repair, certify, or alter the work ETL deployment or its existing staging data.
