# Analytical preparation

Issue #12 provides the repository-owned analytical preparation layer for the
independent official ENOE staging table. It is limited to the 2023 Q1--2025 Q4
core window and to the provisional Jalisco universe: complete interview,
accepted residence, age 15--98, occupied, and `POS_OCU = 1`. The unit of
analysis is a person-quarter.

The layer is the PostgreSQL view
`analysis.enoe_person_quarter_prepared`. It retains every staging column,
including questionnaire-specific `p3i`, the complete source key, and
`source_archive_sha256`. It adds derived columns without modifying or replacing
raw source values.

## Derived fields

The view implements the approved rules in the
[variable dictionary](variable-dictionary.md):

- `income_exact`, `income_exact_observed`, `income_missing_reason`,
  `income_band`, and `income_band_state` keep exact-income availability separate
  from ENOE's ordered income band. A stored `ingocup = 0` is never zero income.
- `weekly_hours` and `hours_missing_reason` distinguish positive reference-week
  hours from temporary absence, unspecified hours, and a missing source value.
- `has_health_access`, `health_access_state`, `has_other_benefits`, and
  `other_benefits_state` keep observed absence separate from unspecified and
  missing protection responses.
- `has_written_contract`, `contract_type`, and `contract_type_state` use
  `tip_con`; `p3i` is not used as a cross-quarter contract feature.

No field imputes values, encodes unknown values as a substantive deprivation, or
fits a model. `analysis_weight` is the retained positive quarterly `fac_tri`.

## Run the guardrail

After the core window is ingested and migrations are current, run:

```bash
just enoe-prepare
```

The command checks every core quarter before emitting JSON. It fails closed if a
quarter is missing; source archive provenance is absent or nonunique; the staged
universe differs from the approved predicate; or the governed income, hours,
contract, health-access, or other-benefits codes are invalid. Its output contains
only period-level record counts, positive-weight totals, and archive hashes.
Do not commit its generated output.

This command does not repair or certify the external work staging table. It
provides the prerequisite preparation evidence for the independent path; model
fitting remains out of scope until that evidence is reviewed.
