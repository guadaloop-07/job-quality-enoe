ALTER TABLE staging.enoe_person_quarter
    ADD COLUMN IF NOT EXISTS rama text,
    ADD COLUMN IF NOT EXISTS c_ocu11c text,
    ADD COLUMN IF NOT EXISTS emple7c text;

DROP VIEW IF EXISTS analysis.enoe_weighted_profile;
DROP VIEW IF EXISTS analysis.enoe_person_quarter_prepared;

CREATE VIEW analysis.enoe_person_quarter_prepared AS
SELECT
    source.*,
    CASE WHEN source.ingocup ~ '^[0-9]+$' AND source.ingocup::numeric BETWEEN 1 AND 999998
        THEN source.ingocup::numeric END AS income_exact,
    CASE WHEN source.ingocup ~ '^[0-9]+$' AND source.ingocup::numeric BETWEEN 1 AND 999998
        THEN true ELSE false END AS income_exact_observed,
    CASE WHEN source.ingocup = '0' THEN 'stored_zero'
        WHEN source.ingocup IS NULL THEN 'missing' END AS income_missing_reason,
    CASE WHEN source.ing7c IN ('1', '2', '3', '4', '5', '6') THEN source.ing7c::smallint END
        AS income_band,
    CASE WHEN source.ing7c IN ('1', '2', '3', '4', '5') THEN 'observed_band'
        WHEN source.ing7c = '6' THEN 'no_income'
        WHEN source.ing7c = '7' THEN 'unspecified'
        WHEN source.ing7c IS NULL THEN 'missing' END AS income_band_state,
    CASE WHEN source.hrsocup ~ '^[0-9]+$' AND source.hrsocup::integer BETWEEN 1 AND 168
        THEN source.hrsocup::smallint END AS weekly_hours,
    CASE WHEN source.hrsocup = '0' AND source.dur9c = '1' THEN 'temporary_absence'
        WHEN source.hrsocup = '0' AND source.dur9c = '9' THEN 'unspecified'
        WHEN source.hrsocup IS NULL THEN 'missing' END AS hours_missing_reason,
    CASE source.seg_soc WHEN '1' THEN true WHEN '2' THEN false END AS has_health_access,
    CASE WHEN source.seg_soc IN ('1', '2') THEN 'observed'
        WHEN source.seg_soc = '3' THEN 'unspecified'
        WHEN source.seg_soc IS NULL THEN 'missing' END AS health_access_state,
    CASE source.pre_asa WHEN '1' THEN true WHEN '2' THEN false END AS has_other_benefits,
    CASE WHEN source.pre_asa IN ('1', '2') THEN 'observed'
        WHEN source.pre_asa = '3' THEN 'unspecified'
        WHEN source.pre_asa IS NULL THEN 'missing' END AS other_benefits_state,
    CASE WHEN source.tip_con IN ('1', '2', '3', '4') THEN true
        WHEN source.tip_con = '5' THEN false END AS has_written_contract,
    CASE source.tip_con WHEN '2' THEN 'temporary' WHEN '3' THEN 'indefinite' END AS contract_type,
    CASE WHEN source.tip_con IN ('2', '3') THEN 'observed_type'
        WHEN source.tip_con IN ('1', '4') THEN 'type_unspecified'
        WHEN source.tip_con = '5' THEN 'not_applicable'
        WHEN source.tip_con = '6' THEN 'unspecified'
        WHEN source.tip_con IS NULL THEN 'missing' END AS contract_type_state,
    source.fac_tri AS analysis_weight
FROM staging.enoe_person_quarter AS source
WHERE source.survey_year BETWEEN 2023 AND 2025
  AND source.entity = 14
  AND source.r_def = '0'
  AND source.c_res IN ('1', '3')
  AND source.eda ~ '^[0-9]+$'
  AND source.eda::integer BETWEEN 15 AND 98
  AND source.clase2 = '1'
  AND source.pos_ocu = '1';

CREATE VIEW analysis.enoe_weighted_profile AS
WITH cells AS (
    SELECT
        source.survey_year,
        source.survey_quarter,
        source.analysis_weight,
        dimension.classifier,
        dimension.category_code,
        dimension.category_state
    FROM analysis.enoe_person_quarter_prepared AS source
    CROSS JOIN LATERAL (
        VALUES
            ('position_in_occupation', coalesce(source.pos_ocu, '<missing>'),
                CASE WHEN source.pos_ocu IS NULL THEN 'missing' WHEN source.pos_ocu IN ('1','2','3','4') THEN 'valid' WHEN source.pos_ocu = '5' THEN 'unspecified' ELSE 'invalid' END),
            ('employment_formality', coalesce(source.emp_ppal, '<missing>'),
                CASE WHEN source.emp_ppal IS NULL THEN 'missing' WHEN source.emp_ppal IN ('1','2') THEN 'valid' ELSE 'invalid' END),
            ('informal_sector', coalesce(source.tue_ppal, '<missing>'),
                CASE WHEN source.tue_ppal IS NULL THEN 'missing' WHEN source.tue_ppal IN ('1','2') THEN 'valid' ELSE 'invalid' END),
            ('activity_branch', coalesce(source.rama, '<missing>'),
                CASE WHEN source.rama IS NULL THEN 'missing' WHEN source.rama IN ('1','2','3','4','5','6') THEN 'valid' WHEN source.rama = '7' THEN 'unspecified' ELSE 'invalid' END),
            ('occupation_group', coalesce(source.c_ocu11c, '<missing>'),
                CASE WHEN source.c_ocu11c IS NULL THEN 'missing' WHEN source.c_ocu11c IN ('1','2','3','4','5','6','7','8','9','10') THEN 'valid' WHEN source.c_ocu11c = '11' THEN 'unspecified' ELSE 'invalid' END),
            ('income_band', coalesce(source.ing7c, '<missing>'),
                CASE WHEN source.ing7c IS NULL THEN 'missing' WHEN source.ing7c IN ('1','2','3','4','5','6') THEN 'valid' WHEN source.ing7c = '7' THEN 'unspecified' ELSE 'invalid' END),
            ('working_time_duration', coalesce(source.dur9c, '<missing>'),
                CASE WHEN source.dur9c IS NULL THEN 'missing' WHEN source.dur9c IN ('1','2','3','4','5','6','7','8') THEN 'valid' WHEN source.dur9c = '9' THEN 'unspecified' ELSE 'invalid' END),
            ('unit_size', coalesce(source.emple7c, '<missing>'),
                CASE WHEN source.emple7c IS NULL THEN 'missing' WHEN source.emple7c IN ('1','2','3','4','5','6') THEN 'valid' WHEN source.emple7c = '7' THEN 'unspecified' ELSE 'invalid' END),
            ('written_contract', CASE WHEN source.has_written_contract THEN 'with_written_contract' WHEN source.has_written_contract = false THEN 'without_written_contract' WHEN source.tip_con = '6' THEN 'unspecified' ELSE '<missing>' END,
                CASE WHEN source.has_written_contract IS NOT NULL THEN 'valid' WHEN source.tip_con = '6' THEN 'unspecified' ELSE 'missing' END),
            ('contract_type', coalesce(source.contract_type_state, '<missing>'),
                CASE WHEN source.contract_type_state IN ('observed_type','type_unspecified') THEN 'valid' WHEN source.contract_type_state = 'not_applicable' THEN 'not_applicable' WHEN source.contract_type_state = 'unspecified' THEN 'unspecified' WHEN source.contract_type_state = 'missing' THEN 'missing' ELSE 'invalid' END),
            ('employment_health_access', CASE WHEN source.has_health_access THEN 'with_access' WHEN source.has_health_access = false THEN 'without_access' WHEN source.health_access_state = 'unspecified' THEN 'unspecified' ELSE '<missing>' END,
                CASE WHEN source.has_health_access IS NOT NULL THEN 'valid' WHEN source.health_access_state = 'unspecified' THEN 'unspecified' ELSE 'missing' END),
            ('non_health_benefits', CASE WHEN source.has_other_benefits THEN 'with_benefits' WHEN source.has_other_benefits = false THEN 'without_benefits' WHEN source.other_benefits_state = 'unspecified' THEN 'unspecified' ELSE '<missing>' END,
                CASE WHEN source.has_other_benefits IS NOT NULL THEN 'valid' WHEN source.other_benefits_state = 'unspecified' THEN 'unspecified' ELSE 'missing' END)
    ) AS dimension (classifier, category_code, category_state)
), aggregates AS (
    SELECT survey_year, survey_quarter, classifier, category_code, category_state,
        count(*) AS unweighted_records, sum(analysis_weight) AS weighted_records
    FROM cells
    GROUP BY survey_year, survey_quarter, classifier, category_code, category_state
)
SELECT survey_year, survey_quarter, classifier, category_code, category_state,
    unweighted_records, weighted_records,
    sum(unweighted_records) OVER denominator AS denominator_unweighted_records,
    sum(weighted_records) OVER denominator AS denominator_weight,
    weighted_records / nullif(sum(weighted_records) OVER denominator, 0) AS weighted_share
FROM aggregates
WINDOW denominator AS (PARTITION BY survey_year, survey_quarter, classifier);

INSERT INTO metadata.catalog_tables (
    schema_name, object_name, object_kind, grain, description, source_scope, is_user_facing
) VALUES (
    'analysis', 'enoe_weighted_profile', 'view',
    'one classifier category per survey quarter',
    'Aggregate-only weighted descriptive ENOE profile with explicit quarterly denominators.',
    'repository-owned official staging, 2023 Q1--2025 Q4; provisional Jalisco domain', true
)
ON CONFLICT (schema_name, object_name) DO UPDATE SET
    object_kind = EXCLUDED.object_kind, grain = EXCLUDED.grain, description = EXCLUDED.description,
    source_scope = EXCLUDED.source_scope, is_user_facing = EXCLUDED.is_user_facing;

INSERT INTO metadata.catalog_code_sets (code_set_name, description, source_reference)
VALUES
    ('rama', 'Economic activity branch.', 'INEGI ENOE. Estructura de la base de datos. Segunda edición. 2025, SDEMT fields 60.'),
    ('c_ocu11c', 'Occupation group classification.', 'INEGI ENOE. Estructura de la base de datos. Segunda edición. 2025, SDEMT field 61.'),
    ('emple7c', 'Establishment worker-count classification.', 'INEGI ENOE. Estructura de la base de datos. Segunda edición. 2025, SDEMT field 64.'),
    ('emp_ppal', 'Formal or informal employment in the main activity.', 'INEGI ENOE. Estructura de la base de datos. Segunda edición. 2025, SDEMT field 107.'),
    ('tue_ppal', 'Main-job unit inside or outside the informal sector.', 'INEGI ENOE. Estructura de la base de datos. Segunda edición. 2025, SDEMT field 108.')
ON CONFLICT (code_set_name) DO UPDATE SET description = EXCLUDED.description, source_reference = EXCLUDED.source_reference;

INSERT INTO metadata.catalog_code_values (code_set_name, code, label, semantic_state)
VALUES
    ('rama','1','Construction','valid'), ('rama','2','Manufacturing','valid'), ('rama','3','Commerce','valid'), ('rama','4','Services','valid'), ('rama','5','Other','valid'), ('rama','6','Agricultural','valid'), ('rama','7','Unspecified activity branch','unspecified'),
    ('c_ocu11c','1','Professionals, technicians, and arts workers','valid'), ('c_ocu11c','2','Education workers','valid'), ('c_ocu11c','3','Officials and managers','valid'), ('c_ocu11c','4','Office workers','valid'), ('c_ocu11c','5','Industrial workers, artisans, and assistants','valid'), ('c_ocu11c','6','Merchants','valid'), ('c_ocu11c','7','Transport operators','valid'), ('c_ocu11c','8','Personal-service workers','valid'), ('c_ocu11c','9','Protection and surveillance workers','valid'), ('c_ocu11c','10','Agricultural workers','valid'), ('c_ocu11c','11','Unspecified occupation','unspecified'),
    ('emple7c','1','One person','valid'), ('emple7c','2','2 to 5 people','valid'), ('emple7c','3','6 to 10 people','valid'), ('emple7c','4','11 to 15 people','valid'), ('emple7c','5','16 to 50 people','valid'), ('emple7c','6','51 or more people','valid'), ('emple7c','7','Unspecified establishment size','unspecified'),
    ('emp_ppal','1','Informal employment','valid'), ('emp_ppal','2','Formal employment','valid'),
    ('tue_ppal','1','Informal sector','valid'), ('tue_ppal','2','Outside the informal sector','valid')
ON CONFLICT (code_set_name, code, period_start) DO UPDATE SET label = EXCLUDED.label, semantic_state = EXCLUDED.semantic_state;

UPDATE metadata.catalog_columns AS columns
SET ordinal_position = ordinal_position + 1000
FROM metadata.catalog_tables AS tables
WHERE columns.catalog_table_id = tables.catalog_table_id
  AND tables.schema_name = 'analysis'
  AND tables.object_name = 'enoe_person_quarter_prepared';

WITH definitions (schema_name, object_name, column_name, classification, description, source_reference, code_set_name) AS (
    VALUES
        ('staging','enoe_person_quarter','rama','raw','Economic activity branch.','SDEM.rama','rama'),
        ('staging','enoe_person_quarter','c_ocu11c','raw','Occupation group.','SDEM.c_ocu11c','c_ocu11c'),
        ('staging','enoe_person_quarter','emple7c','raw','Establishment worker-count category.','SDEM.emple7c','emple7c'),
        ('analysis','enoe_person_quarter_prepared','rama','raw','Retained raw staging field: economic activity branch.','staging.enoe_person_quarter.rama','rama'),
        ('analysis','enoe_person_quarter_prepared','c_ocu11c','raw','Retained raw staging field: occupation group.','staging.enoe_person_quarter.c_ocu11c','c_ocu11c'),
        ('analysis','enoe_person_quarter_prepared','emple7c','raw','Retained raw staging field: establishment worker-count category.','staging.enoe_person_quarter.emple7c','emple7c')
), actual AS (
    SELECT table_schema AS schema_name, table_name AS object_name, column_name, ordinal_position,
        data_type AS physical_type, is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns
    WHERE (table_schema, table_name) IN (('staging','enoe_person_quarter'), ('analysis','enoe_person_quarter_prepared'))
)
INSERT INTO metadata.catalog_columns (catalog_table_id, column_name, ordinal_position, physical_type, is_nullable, classification, description, source_reference, code_set_name)
SELECT tables.catalog_table_id, definitions.column_name, actual.ordinal_position, actual.physical_type, actual.is_nullable, definitions.classification, definitions.description, definitions.source_reference, definitions.code_set_name
FROM definitions JOIN actual USING (schema_name, object_name, column_name)
JOIN metadata.catalog_tables AS tables ON tables.schema_name = definitions.schema_name AND tables.object_name = definitions.object_name
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET ordinal_position = EXCLUDED.ordinal_position, physical_type = EXCLUDED.physical_type, is_nullable = EXCLUDED.is_nullable, classification = EXCLUDED.classification, description = EXCLUDED.description, source_reference = EXCLUDED.source_reference, code_set_name = EXCLUDED.code_set_name;

UPDATE metadata.catalog_columns AS columns
SET ordinal_position = actual.ordinal_position
FROM metadata.catalog_tables AS tables
JOIN information_schema.columns AS actual
  ON actual.table_schema = tables.schema_name
 AND actual.table_name = tables.object_name
WHERE columns.catalog_table_id = tables.catalog_table_id
  AND actual.column_name = columns.column_name
  AND tables.schema_name = 'analysis'
  AND tables.object_name = 'enoe_person_quarter_prepared'
  AND columns.ordinal_position >= 1000;

WITH definitions (column_name, classification, description) AS (
    VALUES
        ('survey_year','key','Survey calendar year.'), ('survey_quarter','key','Survey calendar quarter.'),
        ('classifier','derived','Official classifier or governed prepared field.'), ('category_code','derived','Preserved category code or explicit missing state.'),
        ('category_state','derived','Valid, unspecified, not-applicable, missing, or invalid state.'), ('unweighted_records','derived','Unweighted person-quarter records in the category.'),
        ('weighted_records','derived','Sum of positive quarterly expansion factors in the category.'), ('denominator_unweighted_records','derived','All person-quarter records for the quarter and classifier.'),
        ('denominator_weight','derived','Sum of positive quarterly expansion factors for the quarter and classifier.'), ('weighted_share','derived','Category weighted records divided by its explicit quarterly denominator.')
), actual AS (
    SELECT column_name, ordinal_position, data_type AS physical_type, is_nullable = 'YES' AS is_nullable
    FROM information_schema.columns WHERE table_schema = 'analysis' AND table_name = 'enoe_weighted_profile'
)
INSERT INTO metadata.catalog_columns (catalog_table_id, column_name, ordinal_position, physical_type, is_nullable, classification, description, source_reference)
SELECT tables.catalog_table_id, definitions.column_name, actual.ordinal_position, actual.physical_type, actual.is_nullable, definitions.classification, definitions.description, 'analysis.enoe_person_quarter_prepared'
FROM definitions JOIN actual USING (column_name)
JOIN metadata.catalog_tables AS tables ON tables.schema_name = 'analysis' AND tables.object_name = 'enoe_weighted_profile'
ON CONFLICT (catalog_table_id, column_name) DO UPDATE SET ordinal_position = EXCLUDED.ordinal_position, physical_type = EXCLUDED.physical_type, is_nullable = EXCLUDED.is_nullable, classification = EXCLUDED.classification, description = EXCLUDED.description, source_reference = EXCLUDED.source_reference;
