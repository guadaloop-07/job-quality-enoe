# ENOE variable dictionary and harmonization decisions

This dictionary controls the Jalisco pilot for subordinate paid workers aged 15
or older. The core window is 2023 Q1–2025 Q4; 2026 Q1–Q2 remains an additional
evaluation window. Raw fields are retained, and analytical fields must implement
the rules below only after the source joins are repaired and reloaded.

## Authoritative sources

- INEGI, [*Encuesta Nacional de Ocupación y Empleo (ENOE). Estructura de la
  base de datos. 2025*](https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/doc/enoe_325_fd_c_bas_amp.pdf).
  This document defines the current table key, the ENT to CVE_ENT change,
  valid codes, and the different basic and expanded questionnaires.
- INEGI, [*Encuesta Nacional de Ocupación y Empleo. Conociendo la base de
  datos*](https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/doc/con_basedatos_proy2010.pdf).
- INEGI, [*Encuesta Nacional de Ocupación y Empleo. Reconstrucción de variables.
  2005 a la fecha*](https://www.inegi.org.mx/contenidos/programas/enoe/14ymas/doc/recons_var_conapo2010.pdf).
- Local ETL checkout ede43d965c1539d0293763e9e63e4dfbd7e7df4e, inspected
  clean on 2026-09-10. It is implementation evidence, not the authority for
  survey semantics.

The 2025 structure controls the audited 2025 break. The same mappings are used
provisionally for 2023–2024 and the 2026 evaluation window; the period-specific
official structure must be rechecked before publication if INEGI changes a code.

## Population support

| Field | Source meaning | Decision |
|---|---|---|
| pos_ocu / situacion_trabajo_id | 1 subordinate and paid worker; 2 employer; 3 own-account; 4 unpaid; 5 unspecified | Use 1 in the universe. Preserve the raw code. |
| remune2c | 1 salaried subordinate and paid; 2 subordinate and paid with non-salary perceptions | Retain as a descriptive split. Do not replace the universe predicate without a separate reconciliation. |

## Income and hours

| Field | Official definition and codes | Analytical rule |
|---|---|---|
| ingocup | Monthly income; official valid range 1–999998 pesos | A stored zero is not valid income and must never be interpreted as zero earnings. Set income_exact to missing when ingocup = 0; retain ingocup_raw and an exact-amount availability flag. Positive values remain nominal until the official deflator is added. |
| ing7c | 1 up to one minimum wage; 2 over one to two; 3 over two to three; 4 over three to five; 5 over five; 6 no income; 7 unspecified | Use codes 1–5 as the primary ordered income feature. Code 6 is an explicit no-income category. Code 7 and SQL NULL are missing. Do not assign bracket midpoints as observed income. |
| ing_x_hrs | Published derived income per hour | Do not use the stored value as a model feature. Recompute only from cleaned positive exact income and positive hours, with the monthly-to-weekly convention documented and tested. |
| hrsocup | Hours worked during the reference week; official valid range 1–168 | Use positive values. A stored zero is missing exact hours, not a zero-hour week. Preserve hrsocup_raw and derive a missing-reason flag from dur9c. |
| dur9c | 1 temporarily absent with a work link; 2–8 hour bands; 9 unspecified | For hrsocup = 0, map 1 to temporary_absence and 9 to unspecified. Any other code paired with zero is a validation failure. |

The staging audit found ingocup = 0 together with an informative ing7c band
(1–5) for 17.71–33.57% of candidate quarterly weight. Another 7.21–18.77%
has ing7c = 7. No candidate with ing7c = 6 was observed. Therefore exact
income is too incomplete to be the primary MVP income dimension, while the
ordered bracket remains usable after the source repair. Exact hours are missing
for 2.08–4.16% of candidate records and every observed zero is explained by
dur9c = 1 or 9.

## Contract and protection

| Field | Official definition and codes | Analytical rule |
|---|---|---|
| tip_con | 1 written contract; 2 temporary; 3 permanent/indefinite; 4 written contract, type unspecified; 5 no written contract; 6 unspecified | Primary harmonized contract field. has_written_contract = true for 1–4, false for 5, and missing for 6/NULL. Contract type is temporary for 2, indefinite for 3, and type_unspecified for 1 or 4. |
| pre_asa | Benefits excluding access to health institutions: 1 with; 2 without; 3 unspecified | Primary non-health benefits field. Preserve unspecified separately from absence. |
| seg_soc | Access to health institutions through employment: 1 with; 2 without; 3 unspecified | Primary health-access field. Preserve unspecified separately from no access. |
| medica5c | 1 no benefits; 2 health access only; 3 health and other benefits; 4 other benefits without health access; 5 unspecified | Use as a consistency check against seg_soc and pre_asa, not as a third modeled protection dimension. This avoids double-counting protection. |

## Questionnaire-specific p3i

p3i is not a harmonized contract field:

- In the expanded questionnaire used in first quarters, P3I asks whether the
  worker belongs to a union (1 yes, 2 no, 9 does not know).
- In the basic questionnaire used in the other quarters, P3I asks whether the
  worker has a written contract (1 yes, 2 no, 9 does not know). Contract
  type is collected in subsequent fields.

Exclude p3i from all cross-quarter features and indicators. Retain it only for
questionnaire-aware source and join diagnostics. Use tip_con for the harmonized
contract dimension.

## Required analytical columns

Future preparation must preserve each raw field and add separately named derived
fields. At minimum: income_exact, income_exact_observed, income_band,
income_missing_reason, weekly_hours, hours_missing_reason,
has_health_access, has_other_benefits, has_written_contract, and
contract_type. Unknown and not-applicable states must not be encoded as a
substantive deprivation.
