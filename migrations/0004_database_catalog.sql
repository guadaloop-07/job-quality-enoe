CREATE TABLE IF NOT EXISTS metadata.catalog_tables (
    catalog_table_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schema_name text NOT NULL,
    object_name text NOT NULL,
    object_kind text NOT NULL CHECK (object_kind IN ('table', 'view')),
    grain text NOT NULL,
    description text NOT NULL,
    source_scope text NOT NULL,
    is_user_facing boolean NOT NULL DEFAULT true,
    UNIQUE (schema_name, object_name)
);

CREATE TABLE IF NOT EXISTS metadata.catalog_code_sets (
    code_set_name text PRIMARY KEY,
    description text NOT NULL,
    source_reference text NOT NULL,
    questionnaire_context text
);

CREATE TABLE IF NOT EXISTS metadata.catalog_columns (
    catalog_table_id bigint NOT NULL REFERENCES metadata.catalog_tables (catalog_table_id),
    column_name text NOT NULL,
    ordinal_position integer NOT NULL CHECK (ordinal_position > 0),
    physical_type text NOT NULL,
    is_nullable boolean NOT NULL,
    classification text NOT NULL CHECK (
        classification IN ('key', 'raw', 'derived', 'provenance', 'design', 'technical')
    ),
    description text NOT NULL,
    source_reference text,
    code_set_name text REFERENCES metadata.catalog_code_sets (code_set_name),
    PRIMARY KEY (catalog_table_id, column_name),
    UNIQUE (catalog_table_id, ordinal_position)
);

CREATE TABLE IF NOT EXISTS metadata.catalog_code_values (
    code_set_name text NOT NULL REFERENCES metadata.catalog_code_sets (code_set_name),
    code text NOT NULL,
    label text NOT NULL,
    semantic_state text NOT NULL CHECK (
        semantic_state IN ('valid', 'absence', 'unspecified', 'not_applicable', 'missing')
    ),
    period_start text NOT NULL DEFAULT 'all',
    period_end text,
    PRIMARY KEY (code_set_name, code, period_start)
);

CREATE TABLE IF NOT EXISTS metadata.catalog_lineage (
    catalog_table_id bigint NOT NULL REFERENCES metadata.catalog_tables (catalog_table_id),
    target_column text NOT NULL,
    source_schema_name text NOT NULL,
    source_object_name text NOT NULL,
    source_column_name text NOT NULL,
    relationship text NOT NULL CHECK (relationship IN ('retained', 'derived')),
    transformation_rule text NOT NULL,
    PRIMARY KEY (
        catalog_table_id,
        target_column,
        source_schema_name,
        source_object_name,
        source_column_name
    )
);

INSERT INTO metadata.catalog_tables (
    schema_name, object_name, object_kind, grain, description, source_scope, is_user_facing
) VALUES
    ('metadata', 'schema_migrations', 'table', 'one row per applied migration',
     'Applied migration checksums for the repository-owned database.', 'repository technical metadata', false),
    ('metadata', 'source_archives', 'table', 'one row per source archive hash and period',
     'Official ENOE archive provenance.', 'official archive metadata', true),
    ('metadata', 'ingestion_runs', 'table', 'one row per completed or attempted ingestion',
     'Ingestion execution provenance and aggregate details.', 'repository operational metadata', true),
    ('metadata', 'catalog_tables', 'table', 'one row per cataloged table or view',
     'Versioned database-object catalog.', 'repository catalog metadata', true),
    ('metadata', 'catalog_columns', 'table', 'one row per cataloged physical column',
     'Column definitions, types, semantics, and source references.', 'repository catalog metadata', true),
    ('metadata', 'catalog_code_sets', 'table', 'one row per coded ENOE field definition',
     'Code-set provenance and questionnaire context.', 'repository catalog metadata', true),
    ('metadata', 'catalog_code_values', 'table', 'one row per code meaning and applicability period',
     'Code meanings without survey responses.', 'repository catalog metadata', true),
    ('metadata', 'catalog_lineage', 'table', 'one row per source-to-target relationship',
     'Lineage for retained and derived analytical fields.', 'repository catalog metadata', true),
    ('staging', 'enoe_person_quarter', 'table', 'one ENOE candidate person per survey period',
     'Official ENOE fields for the provisional Jalisco subordinate-paid-worker universe.',
     'official INEGI ENOE CSV archives, 2023 Q1--2025 Q4', true),
    ('analysis', 'enoe_person_quarter_prepared', 'view', 'one prepared candidate person per survey period',
     'Staging fields plus governed analytical derivations; it does not impute values.',
     'repository-owned official staging, 2023 Q1--2025 Q4', true)
ON CONFLICT (schema_name, object_name) DO UPDATE SET
    object_kind = EXCLUDED.object_kind,
    grain = EXCLUDED.grain,
    description = EXCLUDED.description,
    source_scope = EXCLUDED.source_scope,
    is_user_facing = EXCLUDED.is_user_facing;

INSERT INTO metadata.catalog_code_sets (
    code_set_name, description, source_reference, questionnaire_context
) VALUES
    ('pos_ocu', 'Employment position among occupied persons.', 'docs/variable-dictionary.md', NULL),
    ('ing7c', 'Ordered monthly income band.', 'docs/variable-dictionary.md', NULL),
    ('dur9c', 'Reason or band associated with reported hours.', 'docs/variable-dictionary.md', NULL),
    ('tip_con', 'Written contract and contract type.', 'docs/variable-dictionary.md', NULL),
    ('seg_soc', 'Employment-based health-institution access.', 'docs/variable-dictionary.md', NULL),
    ('pre_asa', 'Non-health employment benefits.', 'docs/variable-dictionary.md', NULL),
    ('medica5c', 'Combined health and other-benefits consistency field.', 'docs/variable-dictionary.md', NULL),
    ('p3i_expanded', 'P3I union-membership question.', 'docs/variable-dictionary.md', 'expanded questionnaire, first quarters'),
    ('p3i_basic', 'P3I written-contract question.', 'docs/variable-dictionary.md', 'basic questionnaire, other quarters')
ON CONFLICT (code_set_name) DO UPDATE SET
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    questionnaire_context = EXCLUDED.questionnaire_context;

INSERT INTO metadata.catalog_code_values (
    code_set_name, code, label, semantic_state, period_start, period_end
) VALUES
    ('pos_ocu', '1', 'subordinate and paid worker', 'valid', 'all', NULL),
    ('pos_ocu', '2', 'employer', 'valid', 'all', NULL),
    ('pos_ocu', '3', 'own-account worker', 'valid', 'all', NULL),
    ('pos_ocu', '4', 'unpaid worker', 'valid', 'all', NULL),
    ('pos_ocu', '5', 'unspecified position', 'unspecified', 'all', NULL),
    ('ing7c', '1', 'up to one minimum wage', 'valid', 'all', NULL),
    ('ing7c', '2', 'over one to two minimum wages', 'valid', 'all', NULL),
    ('ing7c', '3', 'over two to three minimum wages', 'valid', 'all', NULL),
    ('ing7c', '4', 'over three to five minimum wages', 'valid', 'all', NULL),
    ('ing7c', '5', 'over five minimum wages', 'valid', 'all', NULL),
    ('ing7c', '6', 'no income', 'absence', 'all', NULL),
    ('ing7c', '7', 'unspecified income band', 'unspecified', 'all', NULL),
    ('dur9c', '1', 'temporarily absent with a work link', 'not_applicable', 'all', NULL),
    ('dur9c', '2-8', 'hours-worked band', 'valid', 'all', NULL),
    ('dur9c', '9', 'unspecified hours', 'unspecified', 'all', NULL),
    ('tip_con', '1', 'written contract, type unspecified', 'valid', 'all', NULL),
    ('tip_con', '2', 'temporary written contract', 'valid', 'all', NULL),
    ('tip_con', '3', 'permanent or indefinite written contract', 'valid', 'all', NULL),
    ('tip_con', '4', 'written contract, type unspecified', 'valid', 'all', NULL),
    ('tip_con', '5', 'no written contract', 'absence', 'all', NULL),
    ('tip_con', '6', 'unspecified contract status', 'unspecified', 'all', NULL),
    ('seg_soc', '1', 'with health-institution access', 'valid', 'all', NULL),
    ('seg_soc', '2', 'without health-institution access', 'absence', 'all', NULL),
    ('seg_soc', '3', 'unspecified health-institution access', 'unspecified', 'all', NULL),
    ('pre_asa', '1', 'with other benefits', 'valid', 'all', NULL),
    ('pre_asa', '2', 'without other benefits', 'absence', 'all', NULL),
    ('pre_asa', '3', 'unspecified other benefits', 'unspecified', 'all', NULL),
    ('medica5c', '1', 'no benefits', 'absence', 'all', NULL),
    ('medica5c', '2', 'health access only', 'valid', 'all', NULL),
    ('medica5c', '3', 'health and other benefits', 'valid', 'all', NULL),
    ('medica5c', '4', 'other benefits without health access', 'valid', 'all', NULL),
    ('medica5c', '5', 'unspecified benefits', 'unspecified', 'all', NULL),
    ('p3i_expanded', '1', 'belongs to a union', 'valid', 'all', NULL),
    ('p3i_expanded', '2', 'does not belong to a union', 'absence', 'all', NULL),
    ('p3i_expanded', '9', 'does not know union status', 'unspecified', 'all', NULL),
    ('p3i_basic', '1', 'has a written contract', 'valid', 'all', NULL),
    ('p3i_basic', '2', 'does not have a written contract', 'absence', 'all', NULL),
    ('p3i_basic', '9', 'does not know contract status', 'unspecified', 'all', NULL)
ON CONFLICT (code_set_name, code, period_start) DO UPDATE SET
    label = EXCLUDED.label,
    semantic_state = EXCLUDED.semantic_state,
    period_end = EXCLUDED.period_end;

WITH definitions (
    column_name, classification, description, source_reference, code_set_name
) AS (
    VALUES
        ('survey_year', 'key', 'Survey calendar year.', 'all', NULL),
        ('survey_quarter', 'key', 'Survey calendar quarter.', 'all', NULL),
        ('tipo', 'key', 'Official ENOE key component TIPO.', 'INEGI ENOE official key', NULL),
        ('mes_cal', 'key', 'Official ENOE key component MES_CAL.', 'INEGI ENOE official key', NULL),
        ('cd_a', 'key', 'Official ENOE key component CD_A.', 'INEGI ENOE official key', NULL),
        ('entity', 'key', 'Normalized official entity code from ENT or CVE_ENT.', 'INEGI ENOE official key', NULL),
        ('con', 'key', 'Official ENOE key component CON.', 'INEGI ENOE official key', NULL),
        ('v_sel', 'key', 'Official ENOE key component V_SEL.', 'INEGI ENOE official key', NULL),
        ('n_hog', 'key', 'Official ENOE key component N_HOG.', 'INEGI ENOE official key', NULL),
        ('h_mud', 'key', 'Official ENOE key component H_MUD.', 'INEGI ENOE official key', NULL),
        ('n_ren', 'key', 'Official ENOE key component N_REN.', 'INEGI ENOE official key', NULL),
        ('r_def', 'raw', 'Interview completion and definition status.', 'SDEM.r_def', NULL),
        ('c_res', 'raw', 'Residence status used by the candidate universe.', 'SDEM.c_res', NULL),
        ('eda', 'raw', 'Age in years; special codes are excluded from the pilot universe.', 'SDEM.eda', NULL),
        ('clase2', 'raw', 'Occupation-class status used by the candidate universe.', 'SDEM.clase2', NULL),
        ('pos_ocu', 'raw', 'Position in occupation.', 'SDEM.pos_ocu', 'pos_ocu'),
        ('fac_tri', 'design', 'Positive quarterly expansion factor; do not pool as a population estimate.', 'SDEM.fac_tri', NULL),
        ('est_d_tri', 'design', 'Sampling-stratum design field.', 'SDEM.est_d_tri', NULL),
        ('upm', 'design', 'Primary sampling unit design field.', 'SDEM.upm', NULL),
        ('remune2c', 'raw', 'Subordinate-worker remuneration subtype.', 'SDEM.remune2c', NULL),
        ('ingocup', 'raw', 'Monthly exact income; zero is not valid observed income.', 'SDEM.ingocup', NULL),
        ('ing7c', 'raw', 'Ordered monthly income band.', 'SDEM.ing7c', 'ing7c'),
        ('hrsocup', 'raw', 'Reference-week hours worked; zero requires a dur9c reason.', 'SDEM.hrsocup', NULL),
        ('dur9c', 'raw', 'Hours reason or band used to interpret zero hrsocup.', 'SDEM.dur9c', 'dur9c'),
        ('tip_con', 'raw', 'Written-contract status and type.', 'SDEM.tip_con', 'tip_con'),
        ('seg_soc', 'raw', 'Employment-based health-institution access.', 'SDEM.seg_soc', 'seg_soc'),
        ('pre_asa', 'raw', 'Benefits other than health-institution access.', 'SDEM.pre_asa', 'pre_asa'),
        ('medica5c', 'raw', 'Combined benefits field retained as a consistency check.', 'SDEM.medica5c', 'medica5c'),
        ('tue_ppal', 'raw', 'Raw ENOE field retained pending informal-employment reconciliation.', 'SDEM.tue_ppal', NULL),
        ('emp_ppal', 'raw', 'Raw ENOE field retained pending informal-employment reconciliation.', 'SDEM.emp_ppal', NULL),
        ('p3i', 'raw', 'Questionnaire-dependent field retained for diagnostics only, not cross-quarter features.', 'COE1.p3i', NULL),
        ('source_archive_sha256', 'provenance', 'SHA-256 of the official archive that supplied the row.', 'metadata.source_archives.content_sha256', NULL),
        ('loaded_at_utc', 'technical', 'Timestamp at which the row was loaded into local staging.', 'all', NULL)
), actual AS (
    SELECT
        columns.column_name,
        columns.ordinal_position,
        CASE
            WHEN columns.data_type = 'numeric' THEN format(
                'numeric(%s,%s)', columns.numeric_precision, columns.numeric_scale
            )
            WHEN columns.character_maximum_length IS NOT NULL THEN format(
                '%s(%s)', columns.data_type, columns.character_maximum_length
            )
            ELSE columns.data_type
        END AS physical_type,
        columns.is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns AS columns
    WHERE columns.table_schema = 'staging' AND columns.table_name = 'enoe_person_quarter'
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
    ON catalog.schema_name = 'staging' AND catalog.object_name = 'enoe_person_quarter'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET
    ordinal_position = EXCLUDED.ordinal_position,
    physical_type = EXCLUDED.physical_type,
    is_nullable = EXCLUDED.is_nullable,
    classification = EXCLUDED.classification,
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    code_set_name = EXCLUDED.code_set_name;

INSERT INTO metadata.catalog_columns (
    catalog_table_id, column_name, ordinal_position, physical_type, is_nullable,
    classification, description, source_reference, code_set_name
)
SELECT
    analysis.catalog_table_id,
    source.column_name,
    actual.ordinal_position,
    actual.physical_type,
    actual.is_nullable,
    source.classification,
    'Retained raw staging field. ' || source.description,
    'staging.enoe_person_quarter.' || source.column_name,
    source.code_set_name
FROM metadata.catalog_columns AS source
JOIN metadata.catalog_tables AS staging
    ON staging.catalog_table_id = source.catalog_table_id
JOIN metadata.catalog_tables AS analysis
    ON analysis.schema_name = 'analysis' AND analysis.object_name = 'enoe_person_quarter_prepared'
JOIN LATERAL (
    SELECT
        columns.column_name,
        columns.ordinal_position,
        CASE
            WHEN columns.data_type = 'numeric' THEN format(
                'numeric(%s,%s)', columns.numeric_precision, columns.numeric_scale
            )
            WHEN columns.character_maximum_length IS NOT NULL THEN format(
                '%s(%s)', columns.data_type, columns.character_maximum_length
            )
            ELSE columns.data_type
        END AS physical_type,
        columns.is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns AS columns
    WHERE columns.table_schema = 'analysis'
      AND columns.table_name = 'enoe_person_quarter_prepared'
      AND columns.column_name = source.column_name
) AS actual ON true
WHERE staging.schema_name = 'staging' AND staging.object_name = 'enoe_person_quarter'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET
    ordinal_position = EXCLUDED.ordinal_position,
    physical_type = EXCLUDED.physical_type,
    is_nullable = EXCLUDED.is_nullable,
    classification = EXCLUDED.classification,
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    code_set_name = EXCLUDED.code_set_name;

WITH definitions (
    column_name, classification, description, source_reference, code_set_name
) AS (
    VALUES
        ('income_exact', 'derived', 'Positive exact monthly income, otherwise NULL.', 'staging.ingocup', NULL),
        ('income_exact_observed', 'derived', 'Whether income_exact is a valid positive observed amount.', 'staging.ingocup', NULL),
        ('income_missing_reason', 'derived', 'Reason exact income is unavailable; stored_zero or missing.', 'staging.ingocup', NULL),
        ('income_band', 'derived', 'Income band codes 1--6; code 7 and NULL are not substantive bands.', 'staging.ing7c', 'ing7c'),
        ('income_band_state', 'derived', 'Observed band, no income, unspecified, or missing state.', 'staging.ing7c', 'ing7c'),
        ('weekly_hours', 'derived', 'Positive reference-week hours, otherwise NULL.', 'staging.hrsocup', NULL),
        ('hours_missing_reason', 'derived', 'Temporary absence, unspecified, or missing reason for hours.', 'staging.hrsocup; staging.dur9c', 'dur9c'),
        ('has_health_access', 'derived', 'Boolean health-institution access; unspecified remains NULL.', 'staging.seg_soc', 'seg_soc'),
        ('health_access_state', 'derived', 'Observed, unspecified, or missing health-access response state.', 'staging.seg_soc', 'seg_soc'),
        ('has_other_benefits', 'derived', 'Boolean non-health benefits; unspecified remains NULL.', 'staging.pre_asa', 'pre_asa'),
        ('other_benefits_state', 'derived', 'Observed, unspecified, or missing other-benefits response state.', 'staging.pre_asa', 'pre_asa'),
        ('has_written_contract', 'derived', 'Boolean written-contract status; unspecified remains NULL.', 'staging.tip_con', 'tip_con'),
        ('contract_type', 'derived', 'Temporary or indefinite written-contract type when observed.', 'staging.tip_con', 'tip_con'),
        ('contract_type_state', 'derived', 'Observed type, type unspecified, not applicable, unspecified, or missing.', 'staging.tip_con', 'tip_con'),
        ('analysis_weight', 'derived', 'Positive quarterly expansion factor retained for analysis.', 'staging.fac_tri', NULL)
), actual AS (
    SELECT
        columns.column_name,
        columns.ordinal_position,
        CASE
            WHEN columns.data_type = 'numeric' THEN format(
                'numeric(%s,%s)', columns.numeric_precision, columns.numeric_scale
            )
            WHEN columns.character_maximum_length IS NOT NULL THEN format(
                '%s(%s)', columns.data_type, columns.character_maximum_length
            )
            ELSE columns.data_type
        END AS physical_type,
        columns.is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns AS columns
    WHERE columns.table_schema = 'analysis' AND columns.table_name = 'enoe_person_quarter_prepared'
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
    ON catalog.schema_name = 'analysis' AND catalog.object_name = 'enoe_person_quarter_prepared'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET
    ordinal_position = EXCLUDED.ordinal_position,
    physical_type = EXCLUDED.physical_type,
    is_nullable = EXCLUDED.is_nullable,
    classification = EXCLUDED.classification,
    description = EXCLUDED.description,
    source_reference = EXCLUDED.source_reference,
    code_set_name = EXCLUDED.code_set_name;

INSERT INTO metadata.catalog_lineage (
    catalog_table_id, target_column, source_schema_name, source_object_name, source_column_name,
    relationship, transformation_rule
)
SELECT
    analysis.catalog_table_id,
    derived.target_column,
    'staging',
    'enoe_person_quarter',
    derived.source_column_name,
    'derived',
    derived.transformation_rule
FROM (
    VALUES
        ('income_exact', 'ingocup', 'Keep values 1--999998; zero and invalid values become NULL.'),
        ('income_exact_observed', 'ingocup', 'True only for valid positive exact income.'),
        ('income_missing_reason', 'ingocup', 'Map zero to stored_zero and NULL to missing.'),
        ('income_band', 'ing7c', 'Keep codes 1--6; code 7 and NULL become NULL.'),
        ('income_band_state', 'ing7c', 'Map codes to observed_band, no_income, unspecified, or missing.'),
        ('weekly_hours', 'hrsocup', 'Keep positive values 1--168; zero and missing become NULL.'),
        ('hours_missing_reason', 'dur9c', 'For zero hours, map 1 to temporary_absence and 9 to unspecified.'),
        ('has_health_access', 'seg_soc', 'Map 1 to true, 2 to false, and 3 or NULL to NULL.'),
        ('has_other_benefits', 'pre_asa', 'Map 1 to true, 2 to false, and 3 or NULL to NULL.'),
        ('has_written_contract', 'tip_con', 'Map 1--4 to true, 5 to false, and 6 or NULL to NULL.'),
        ('contract_type', 'tip_con', 'Map 2 to temporary and 3 to indefinite.'),
        ('hours_missing_reason', 'hrsocup', 'For zero hours, derive a reason from dur9c; otherwise retain missing state.'),
        ('health_access_state', 'seg_soc', 'Map the raw response to observed, unspecified, or missing state.'),
        ('other_benefits_state', 'pre_asa', 'Map the raw response to observed, unspecified, or missing state.'),
        ('contract_type_state', 'tip_con', 'Map the raw response to observed type, unspecified, not applicable, or missing state.'),
        ('analysis_weight', 'fac_tri', 'Retain the positive quarterly expansion factor.')
) AS derived (target_column, source_column_name, transformation_rule)
JOIN metadata.catalog_tables AS analysis
    ON analysis.schema_name = 'analysis' AND analysis.object_name = 'enoe_person_quarter_prepared'
ON CONFLICT DO NOTHING;
