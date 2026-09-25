CREATE TABLE IF NOT EXISTS metadata.profile_classifiers (
    classifier text PRIMARY KEY,
    classifier_label text NOT NULL,
    source_field text NOT NULL,
    source_code_set_name text REFERENCES metadata.catalog_code_sets (code_set_name),
    derivation_rule text NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata.profile_categories (
    classifier text NOT NULL REFERENCES metadata.profile_classifiers (classifier),
    category_code text NOT NULL,
    category_state text NOT NULL CHECK (
        category_state IN ('valid', 'unspecified', 'not_applicable', 'missing')
    ),
    category_label text NOT NULL,
    PRIMARY KEY (classifier, category_code, category_state)
);

INSERT INTO metadata.profile_classifiers (
    classifier, classifier_label, source_field, source_code_set_name, derivation_rule
) VALUES
    ('position_in_occupation', 'Position in occupation', 'pos_ocu', 'pos_ocu',
     'Preserve POS_OCU codes; the approved universe retains code 1 only.'),
    ('employment_formality', 'Employment formality', 'emp_ppal', 'emp_ppal',
     'Preserve EMP_PPAL codes; do not equate this classifier with informal_sector.'),
    ('informal_sector', 'Informal sector', 'tue_ppal', 'tue_ppal',
     'Preserve TUE_PPAL codes for the main-job unit.'),
    ('activity_branch', 'Activity branch', 'rama', 'rama', 'Preserve RAMA codes.'),
    ('occupation_group', 'Occupation group', 'c_ocu11c', 'c_ocu11c',
     'Preserve C_OCU11C codes.'),
    ('income_band', 'Income band', 'ing7c', 'ing7c',
     'Preserve ING7C codes; code 6 is an explicit no-income category.'),
    ('working_time_duration', 'Working-time duration', 'dur9c', 'dur9c',
     'Preserve DUR9C codes, including temporary absence with a work link.'),
    ('unit_size', 'Unit size', 'emple7c', 'emple7c', 'Preserve EMPLE7C codes.'),
    ('written_contract', 'Written contract', 'tip_con', 'tip_con',
     'Derive written-contract status from TIP_CON.'),
    ('contract_type', 'Contract type availability', 'contract_type_state', 'tip_con',
     'Preserve the governed contract_type_state, not the temporary or indefinite subtype.'),
    ('employment_health_access', 'Employment-based health access', 'has_health_access', 'seg_soc',
     'Derive access status from SEG_SOC and its response state.'),
    ('non_health_benefits', 'Non-health benefits', 'has_other_benefits', 'pre_asa',
     'Derive benefit status from PRE_ASA and its response state.')
ON CONFLICT (classifier) DO UPDATE SET
    classifier_label = EXCLUDED.classifier_label,
    source_field = EXCLUDED.source_field,
    source_code_set_name = EXCLUDED.source_code_set_name,
    derivation_rule = EXCLUDED.derivation_rule;

INSERT INTO metadata.profile_categories (
    classifier, category_code, category_state, category_label
)
SELECT
    classifiers.classifier,
    values.code,
    CASE WHEN values.semantic_state = 'unspecified' THEN 'unspecified' ELSE 'valid' END,
    values.label
FROM metadata.profile_classifiers AS classifiers
JOIN metadata.catalog_code_values AS values
    ON values.code_set_name = classifiers.source_code_set_name
WHERE classifiers.classifier IN (
    'position_in_occupation',
    'employment_formality',
    'informal_sector',
    'activity_branch',
    'occupation_group',
    'income_band',
    'working_time_duration',
    'unit_size'
)
ON CONFLICT (classifier, category_code, category_state) DO UPDATE SET
    category_label = EXCLUDED.category_label;

INSERT INTO metadata.profile_categories (
    classifier, category_code, category_state, category_label
)
SELECT classifier, '<missing>', 'missing', 'Missing response'
FROM metadata.profile_classifiers
WHERE classifier IN (
    'position_in_occupation',
    'employment_formality',
    'informal_sector',
    'activity_branch',
    'occupation_group',
    'income_band',
    'working_time_duration',
    'unit_size'
)
ON CONFLICT (classifier, category_code, category_state) DO UPDATE SET
    category_label = EXCLUDED.category_label;

INSERT INTO metadata.profile_categories (
    classifier, category_code, category_state, category_label
) VALUES
    ('written_contract', 'with_written_contract', 'valid', 'With written contract'),
    ('written_contract', 'without_written_contract', 'valid', 'Without written contract'),
    ('written_contract', 'unspecified', 'unspecified', 'Unspecified written-contract status'),
    ('written_contract', '<missing>', 'missing', 'Missing written-contract response'),
    ('contract_type', 'observed_type', 'valid', 'Observed contract type'),
    ('contract_type', 'type_unspecified', 'valid', 'Written contract with unspecified type'),
    ('contract_type', 'not_applicable', 'not_applicable', 'Not applicable: no written contract'),
    ('contract_type', 'unspecified', 'unspecified', 'Unspecified contract type'),
    ('contract_type', 'missing', 'missing', 'Missing contract-type response'),
    ('employment_health_access', 'with_access', 'valid', 'With employment-based health access'),
    ('employment_health_access', 'without_access', 'valid', 'Without employment-based health access'),
    ('employment_health_access', 'unspecified', 'unspecified', 'Unspecified employment-based health access'),
    ('employment_health_access', '<missing>', 'missing', 'Missing health-access response'),
    ('non_health_benefits', 'with_benefits', 'valid', 'With non-health benefits'),
    ('non_health_benefits', 'without_benefits', 'valid', 'Without non-health benefits'),
    ('non_health_benefits', 'unspecified', 'unspecified', 'Unspecified non-health benefits'),
    ('non_health_benefits', '<missing>', 'missing', 'Missing non-health-benefits response')
ON CONFLICT (classifier, category_code, category_state) DO UPDATE SET
    category_label = EXCLUDED.category_label;

CREATE OR REPLACE VIEW analysis.enoe_weighted_profile_labeled AS
SELECT
    profile.*,
    classifiers.classifier_label,
    categories.category_label,
    classifiers.source_field,
    classifiers.source_code_set_name,
    classifiers.derivation_rule
FROM analysis.enoe_weighted_profile AS profile
LEFT JOIN metadata.profile_classifiers AS classifiers
    ON classifiers.classifier = profile.classifier
LEFT JOIN metadata.profile_categories AS categories
    ON categories.classifier = profile.classifier
   AND categories.category_code = profile.category_code
   AND categories.category_state = profile.category_state;

INSERT INTO metadata.catalog_tables (
    schema_name, object_name, object_kind, grain, description, source_scope, is_user_facing
) VALUES
    ('metadata', 'profile_classifiers', 'table', 'one row per weighted-profile classifier',
     'Classifier labels, source fields, source code sets, and derivation rules for the weighted profile.',
     'repository profile metadata', true),
    ('metadata', 'profile_categories', 'table', 'one row per valid profile classifier category and state',
     'Readable labels for categories emitted by the weighted profile.',
     'repository profile metadata', true),
    ('analysis', 'enoe_weighted_profile_labeled', 'view', 'one labeled classifier category per survey quarter',
     'Weighted profile aggregates with catalog labels and source metadata; it does not alter profile calculations.',
     'repository-owned official staging, 2023 Q1--2025 Q4; provisional Jalisco domain', true)
ON CONFLICT (schema_name, object_name) DO UPDATE SET
    object_kind = EXCLUDED.object_kind,
    grain = EXCLUDED.grain,
    description = EXCLUDED.description,
    source_scope = EXCLUDED.source_scope,
    is_user_facing = EXCLUDED.is_user_facing;

INSERT INTO metadata.catalog_columns (
    catalog_table_id, column_name, ordinal_position, physical_type, is_nullable,
    classification, description, source_reference, code_set_name
)
SELECT
    labeled.catalog_table_id,
    source.column_name,
    source.ordinal_position,
    source.physical_type,
    source.is_nullable,
    source.classification,
    source.description,
    'analysis.enoe_weighted_profile.' || source.column_name,
    source.code_set_name
FROM metadata.catalog_columns AS source
JOIN metadata.catalog_tables AS profile
    ON profile.catalog_table_id = source.catalog_table_id
JOIN metadata.catalog_tables AS labeled
    ON labeled.schema_name = 'analysis' AND labeled.object_name = 'enoe_weighted_profile_labeled'
WHERE profile.schema_name = 'analysis' AND profile.object_name = 'enoe_weighted_profile'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET
    ordinal_position = EXCLUDED.ordinal_position,
    physical_type = EXCLUDED.physical_type,
    is_nullable = EXCLUDED.is_nullable,
    classification = EXCLUDED.classification,
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    code_set_name = EXCLUDED.code_set_name;

WITH definitions (column_name, classification, description, source_reference, code_set_name) AS (
    VALUES
        ('classifier_label', 'derived', 'Readable weighted-profile classifier label.',
         'metadata.profile_classifiers.classifier_label', NULL),
        ('category_label', 'derived', 'Readable category label for classifier, code, and state.',
         'metadata.profile_categories.category_label', NULL),
        ('source_field', 'provenance', 'Prepared-view field or governed state used by the classifier.',
         'metadata.profile_classifiers.source_field', NULL),
        ('source_code_set_name', 'provenance', 'Original ENOE code set where applicable.',
         'metadata.profile_classifiers.source_code_set_name', NULL),
        ('derivation_rule', 'provenance', 'Rule that maps source values to the profile classifier.',
         'metadata.profile_classifiers.derivation_rule', NULL)
), actual AS (
    SELECT column_name, ordinal_position, data_type AS physical_type, is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'analysis' AND table_name = 'enoe_weighted_profile_labeled'
)
INSERT INTO metadata.catalog_columns (
    catalog_table_id, column_name, ordinal_position, physical_type, is_nullable,
    classification, description, source_reference, code_set_name
)
SELECT
    tables.catalog_table_id,
    definitions.column_name,
    actual.ordinal_position,
    actual.physical_type,
    actual.is_nullable,
    definitions.classification,
    definitions.description,
    definitions.source_reference,
    definitions.code_set_name
FROM definitions
JOIN actual USING (column_name)
JOIN metadata.catalog_tables AS tables
    ON tables.schema_name = 'analysis' AND tables.object_name = 'enoe_weighted_profile_labeled'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET
    ordinal_position = EXCLUDED.ordinal_position,
    physical_type = EXCLUDED.physical_type,
    is_nullable = EXCLUDED.is_nullable,
    classification = EXCLUDED.classification,
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    code_set_name = EXCLUDED.code_set_name;
