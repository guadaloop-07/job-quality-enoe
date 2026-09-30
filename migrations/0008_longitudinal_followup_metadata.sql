ALTER TABLE staging.enoe_person_quarter
    ADD COLUMN IF NOT EXISTS n_ent text;

INSERT INTO metadata.catalog_code_sets (
    code_set_name, description, source_reference, questionnaire_context
) VALUES (
    'n_ent',
    'ENOE interview visit number within the sampled dwelling follow-up cycle.',
    'INEGI ENOE. Estructura de la base de datos, SDEM N_ENT.',
    'Follow-up metadata; it is not a person identifier.'
)
ON CONFLICT (code_set_name) DO UPDATE SET
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    questionnaire_context = EXCLUDED.questionnaire_context;

INSERT INTO metadata.catalog_code_values (code_set_name, code, label, semantic_state)
VALUES
    ('n_ent', '1', 'First interview visit', 'valid'),
    ('n_ent', '2', 'Second interview visit', 'valid'),
    ('n_ent', '3', 'Third interview visit', 'valid'),
    ('n_ent', '4', 'Fourth interview visit', 'valid'),
    ('n_ent', '5', 'Fifth interview visit', 'valid')
ON CONFLICT (code_set_name, code, period_start) DO UPDATE SET
    label = EXCLUDED.label,
    semantic_state = EXCLUDED.semantic_state;

WITH definitions (
    column_name, classification, description, source_reference, code_set_name
) AS (
    VALUES (
        'n_ent',
        'design',
        'Interview visit number retained only for aggregate longitudinal follow-up diagnostics; not a person identifier or model feature.',
        'SDEM.n_ent',
        'n_ent'
    )
), actual AS (
    SELECT
        columns.column_name,
        columns.ordinal_position,
        columns.data_type AS physical_type,
        columns.is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns AS columns
    WHERE columns.table_schema = 'staging'
      AND columns.table_name = 'enoe_person_quarter'
)
INSERT INTO metadata.catalog_columns (
    catalog_table_id, column_name, ordinal_position, physical_type, is_nullable,
    classification, description, source_reference, code_set_name
)
SELECT
    catalog.catalog_table_id, definitions.column_name, actual.ordinal_position,
    actual.physical_type, actual.is_nullable, definitions.classification,
    definitions.description, definitions.source_reference, definitions.code_set_name
FROM definitions
JOIN actual USING (column_name)
JOIN metadata.catalog_tables AS catalog
    ON catalog.schema_name = 'staging'
   AND catalog.object_name = 'enoe_person_quarter'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET
    ordinal_position = EXCLUDED.ordinal_position,
    physical_type = EXCLUDED.physical_type,
    is_nullable = EXCLUDED.is_nullable,
    classification = EXCLUDED.classification,
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    code_set_name = EXCLUDED.code_set_name;
