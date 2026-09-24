# Database catalog

The database catalog is versioned in
[`migrations/0004_database_catalog.sql`](../migrations/0004_database_catalog.sql).
It is seeded by migration and is not maintained through manual DBeaver edits.
It contains metadata only: no ENOE rows, credentials, downloads, or generated
analysis output.

## Catalog objects

| Object | Purpose |
|---|---|
| `metadata.catalog_tables` | Purpose, grain, scope, and kind of each cataloged table or view. |
| `metadata.catalog_columns` | Physical type, nullability, classification, description, source reference, and optional code set for each column. |
| `metadata.catalog_code_sets` | Provenance and questionnaire context for coded fields. |
| `metadata.catalog_code_values` | Valid, absence, unspecified, and not-applicable code meanings. |
| `metadata.catalog_lineage` | Retained and derived relationships from staging into analytical fields. |
| `metadata.profile_classifiers` | Labels, source fields, code sets, and derivation rules for the 12 weighted-profile classifiers. |
| `metadata.profile_categories` | Labels for every valid `classifier`, `category_code`, and `category_state` combination emitted by the weighted profile. |

`metadata.catalog_columns` covers every column in the user-facing
`staging.enoe_person_quarter` table and
`analysis.enoe_person_quarter_prepared` view. The `p3i` field deliberately has
no cross-quarter code set because its question changes between questionnaires.

`analysis.enoe_weighted_profile_labeled` preserves every aggregate measure from
`analysis.enoe_weighted_profile` and adds classifier and category labels,
source-field provenance, code-set provenance, and derivation rules. It is the
recommended DBeaver interface for readable profile aggregates.

## DBeaver queries

Inspect one object's columns and meanings:

```sql
SELECT
  columns.ordinal_position,
  columns.column_name,
  columns.physical_type,
  columns.is_nullable,
  columns.classification,
  columns.description,
  columns.source_reference,
  columns.code_set_name
FROM metadata.catalog_columns AS columns
JOIN metadata.catalog_tables AS objects
  ON objects.catalog_table_id = columns.catalog_table_id
WHERE objects.schema_name = 'analysis'
  AND objects.object_name = 'enoe_person_quarter_prepared'
ORDER BY columns.ordinal_position;
```

Inspect the meanings of a coded field:

```sql
SELECT code, label, semantic_state, period_start, period_end
FROM metadata.catalog_code_values
WHERE code_set_name = 'tip_con'
ORDER BY code;
```

Inspect every profile category and its source rule:

```sql
SELECT
  classifiers.classifier,
  classifiers.classifier_label,
  categories.category_code,
  categories.category_state,
  categories.category_label,
  classifiers.source_field,
  classifiers.source_code_set_name,
  classifiers.derivation_rule
FROM metadata.profile_categories AS categories
JOIN metadata.profile_classifiers AS classifiers
  ON classifiers.classifier = categories.classifier
ORDER BY classifiers.classifier, categories.category_state, categories.category_code;
```

Inspect the derivation of analytical fields:

```sql
SELECT target_column, source_object_name, source_column_name, transformation_rule
FROM metadata.catalog_lineage AS lineage
JOIN metadata.catalog_tables AS objects
  ON objects.catalog_table_id = lineage.catalog_table_id
WHERE objects.schema_name = 'analysis'
  AND objects.object_name = 'enoe_person_quarter_prepared'
ORDER BY target_column, source_column_name;
```

Run `just catalog-validate` after migrations. It fails when the user-facing
staging or analytical schema gains an uncataloged column or retains a catalog
entry for a removed column.
