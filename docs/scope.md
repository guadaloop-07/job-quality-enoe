# Pilot scope

Approved on 2026-09-08. Core window: 2023 Q1–2025 Q4. Audit window:
2023 Q1–2026 Q2. Additional quarters are candidates for temporal evaluation,
conditional on comparable definitions and usable coverage.

The question is whether interpretable, stable profiles of employment conditions
can be identified among subordinate paid workers aged 15 or older in Jalisco.
Profiles are analytical constructs, not official INEGI categories or a universal
ranking of job quality. The unit is a person-quarter, not a unique person across
the pooled window.

The provisional population filter is `entidad_id = 14`, `r_def = 0`,
`c_res IN (1, 3)`, `eda BETWEEN 15 AND 98`, `clase2 = 1`, and
`situacion_trabajo_id = 1`. The upper age bound excludes special codes; verify
source definitions before finalizing preparation.

Central dimensions are income, working time, health access, aggregate benefits
and contract. Audit raw `ingocup`, `hrsocup`, `seg_soc`, `medica5c`, `pre_asa`,
`tip_con`, and `p3i`. SQL NULL is not equivalent to survey nonresponse: zero,
unknown, not applicable and special codes remain distinct until their
period-specific definitions are verified. Income remains nominal and the scope
of working time remains unverified at this stage.

Use positive quarterly `fac` for diagnostic weighted totals and report invalid
weights separately. Quarterly totals are not pooled population estimates.
Preserve `est_d_tri`, `upm`, household keys and interview identifiers.

Provisional protocol: develop on 2023–2024 with internal evaluation, evaluate
temporally on 2025, and assess transport to 2026 Q1–Q2. Freeze preprocessing
before temporal evaluation and confirm repeat-household controls before
implementing splits. Do not compare partial-year and full-year totals.

State-level reporting is the default. Municipal identifiers do not establish
municipal representativeness. Additional domains require defensible inference
and precision. No municipal rankings, individual transitions, national extension,
model fitting or public deployment are included in this initial change.

Gate A remains open until coverage, code semantics, join integrity and usable
contract/protection dimensions are established. Resolve `tue_ppal` versus
`emp_ppal` before using informal employment as a benchmark.
