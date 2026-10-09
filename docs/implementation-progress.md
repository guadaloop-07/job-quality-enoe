# Implementation progress

Reference: implementation proposal dated 2026-09-07, approved scope update dated
2026-09-08. The original 48-block plan remains the roadmap; this tracker records
actual deliverables rather than treating the infrastructure baseline as analysis.
For the current distinction between the independent project path and the
deployed work ETL, see the [Gate A decision](gate-a-decision.md).

| Block | Status | Evidence / next action |
|---|---|---|
| 01 Scope | Complete | [Scope](scope.md), including expanded audit window |
| 02 Environment | Complete for database foundation | Python/uv/CI plus an isolated [PostgreSQL 17 environment](local-database.md); add analysis dependencies as needed |
| 03 Access and schema | Complete for the independent core window | [Official ingestion](official-enoe-ingestion.md), [source manifest](official-enoe-source-manifest.md), and [12-period reconciliation](official-enoe-reconciliation.md) |
| 04 Coverage and candidate population | Complete, provisional universe | [Independent reconciliation](official-enoe-reconciliation.md), [analytical preparation](analytical-preparation.md), and historical [external-ETL evidence](audit-findings.md) |
| 05 Income and hours definitions | Complete for Gate A | [Source-backed definitions](variable-dictionary.md); retain income bands and distinguish temporary-absence hours |
| 06 Contract and protection | Complete for Gate A | Use tip_con, pre_asa and seg_soc; exclude p3i as a cross-quarter feature |
| 07 Join integrity | Complete for independent 2023--2025 staging | Official-key source validation and [aggregate reconciliation](official-enoe-reconciliation.md); work ETL repair remains outside this repository |
| 08 Nonresponse and Gate A | Complete for the independent table | [Decision](gate-a-decision.md) and [analytical preparation](analytical-preparation.md); the external work table remains blocked |
| 09–48 | In progress | Issues #17 and #20 implement the weighted descriptive protocol and aggregate baseline; #22 records a passed source-integrity gate for separate 2026 Q1--Q2 evaluation without extending the core period; #24 adds readable profile-category metadata; #28 fixes the pre-fit model contract; #30 implements guarded fitting inputs and temporal safeguards; #32 adds aggregate longitudinal follow-up evidence; #34 fixes the primary and sensitivity split hierarchy; #38 authorizes the guarded candidate dossier; #41 pre-specifies interpretability review; and #50 implements the one-time final held-out evaluation interface. These controls authorize no published model, individual score, or public deployment. |

Tracking issues: #3, #5, #7, #8, #12, #17, #20, #22, #24, #28, #30, #32, #34,
#38, #41, #48, and #50. No unattended computations remain. Active duration was
not instrumented; do not interpret elapsed conversation time as measured work hours.
The aggregate live query took under five seconds on this run; costs are not
guaranteed for other databases. The weighted descriptive profile and its
aggregate baseline are available from the prepared independent table. Guarded
candidate fitting and fixed-solution robustness are available under the model
contract; final held-out evaluation uses 2026 only after the specification is
frozen.
