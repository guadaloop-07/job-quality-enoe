# Gate A decision

**Decision on 2026-09-10: source data is viable, but the deployed staging table
is blocked for analytical preparation until the SDEM–COE joins and storage key
are repaired and the approved window is reloaded.**

## What is accepted

- Core period: 2023 Q1–2025 Q4.
- Additional evaluation: 2026 Q1–Q2.
- Population: Jalisco residents aged 15–98 with complete/accepted residence,
  occupied, and pos_ocu = 1 (subordinate and paid).
- Income: ordered ing7c bands are the primary feature. Exact positive
  ingocup is secondary and missing whenever the stored value is zero.
- Hours: positive hrsocup, with zero mapped to a missing reason using dur9c.
- Health access: seg_soc.
- Other benefits: pre_asa.
- Written contract and type: tip_con.
- medica5c: validation and description only, not an additional modeled
  protection dimension.
- p3i: excluded from cross-quarter features because its question changes
  between expanded and basic questionnaires.

## Blocking defect

The official raw files pass one-to-one SDEM–COE1 and SDEM–COE2 checks for the
three audited periods. The current ETL does not use the official key and, from
2025 Q3, drops the entity from the join. The load then ignores storage-key
conflicts. Consequently, the staged p3i discontinuity is predominantly a join
artifact, and the database may contain wrong COE values and omitted SDEM rows.
Post-ingestion uniqueness cannot detect records that were discarded.

Severity is **critical** for contract variables and any COE-derived analysis;
confidence is high because the official-key joins are complete while the current
key reproduces multiple and wrong-entity matches. The impact is not limited to
p3i: COE2 is affected, and the nonofficial storage key collides in 2023 Q1 and
2025 Q3 among the tested periods.

## Reopening criteria

Gate A passes only after all of the following are evidenced:

1. The ETL requires the official key with canonical entity naming and validated
   one-to-one joins.
2. Storage uniqueness preserves TIPO and MES_CAL and does not silently drop
   source collisions.
3. The database is reloaded for 2023 Q1–2026 Q2 from identified source hashes.
4. Raw candidate and staged candidate counts reconcile by quarter, or every
   difference is explained and accepted.
5. The aggregate staging audit and representative raw join audit pass again.
6. The analytical preparation implements the variable rules in
   [the dictionary](variable-dictionary.md) with tests.

Blocks 09–16 and all model work remain stopped. Narrowing the period would not
resolve the incorrect key: 2023 Q1 already demonstrates storage collisions and
multiple COE matches, while 2025 Q2 only passes under the current key by chance.
