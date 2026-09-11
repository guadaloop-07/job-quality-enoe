# Implementation progress

Reference: implementation proposal dated 2026-09-07, approved scope update dated
2026-09-08. The original 48-block plan remains the roadmap; this tracker records
actual deliverables rather than treating the infrastructure baseline as analysis.

| Block | Status | Evidence / next action |
|---|---|---|
| 01 Scope | Complete | [Scope](scope.md), including expanded audit window |
| 02 Environment | Complete for database foundation | Python/uv/CI plus an isolated [PostgreSQL 17 environment](local-database.md); add analysis dependencies as needed |
| 03 Access and schema | Foundation complete; empty by design | Versioned metadata and staging schemas are project-owned; official source ingestion is pending #8 |
| 04 Coverage and candidate population | Complete, provisional universe | [Quarterly evidence](audit-findings.md) and cumulative funnel |
| 05 Income and hours definitions | Complete for Gate A | [Source-backed definitions](variable-dictionary.md); retain income bands and distinguish temporary-absence hours |
| 06 Contract and protection | Complete for Gate A | Use tip_con, pre_asa and seg_soc; exclude p3i as a cross-quarter feature |
| 07 Join integrity | Diagnosis complete; repair pending | [Raw audit](raw-join-audit.md) proves the official key is safe and the deployed ETL key is not |
| 08 Nonresponse and Gate A | Complete: blocked | [Decision](gate-a-decision.md) requires upstream repair, reload and reconciliation |
| 09–48 | Not started; blocked | Resume only after the Gate A reopening criteria pass |

Tracking issues: #3, #5, #7, and #8. No unattended computations remain. Active duration was not
instrumented; do not interpret elapsed conversation time as measured work hours.
The aggregate live query took under five seconds on this run; costs are not
guaranteed for other databases. Next deliverable: ingest and validate official
2023--2025 archives in the independent staging environment (#8).
