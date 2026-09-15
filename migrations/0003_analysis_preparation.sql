CREATE SCHEMA IF NOT EXISTS analysis;

CREATE OR REPLACE VIEW analysis.enoe_person_quarter_prepared AS
SELECT
    source.*,
    CASE
        WHEN CASE
            WHEN source.ingocup ~ '^[0-9]+$' THEN source.ingocup::numeric
            ELSE -1
        END BETWEEN 1 AND 999998
            THEN source.ingocup::numeric
        ELSE NULL
    END AS income_exact,
    CASE
        WHEN source.ingocup ~ '^[0-9]+$' THEN source.ingocup::numeric BETWEEN 1 AND 999998
        ELSE false
    END AS income_exact_observed,
    CASE
        WHEN source.ingocup = '0' THEN 'stored_zero'
        WHEN source.ingocup IS NULL THEN 'missing'
        ELSE NULL
    END AS income_missing_reason,
    CASE
        WHEN source.ing7c IN ('1', '2', '3', '4', '5', '6') THEN source.ing7c::smallint
        ELSE NULL
    END AS income_band,
    CASE
        WHEN source.ing7c IN ('1', '2', '3', '4', '5') THEN 'observed_band'
        WHEN source.ing7c = '6' THEN 'no_income'
        WHEN source.ing7c = '7' THEN 'unspecified'
        WHEN source.ing7c IS NULL THEN 'missing'
        ELSE NULL
    END AS income_band_state,
    CASE
        WHEN CASE
            WHEN source.hrsocup ~ '^[0-9]+$' THEN source.hrsocup::integer
            ELSE -1
        END BETWEEN 1 AND 168
            THEN source.hrsocup::smallint
        ELSE NULL
    END AS weekly_hours,
    CASE
        WHEN source.hrsocup = '0' AND source.dur9c = '1' THEN 'temporary_absence'
        WHEN source.hrsocup = '0' AND source.dur9c = '9' THEN 'unspecified'
        WHEN source.hrsocup IS NULL THEN 'missing'
        ELSE NULL
    END AS hours_missing_reason,
    CASE source.seg_soc
        WHEN '1' THEN true
        WHEN '2' THEN false
        ELSE NULL
    END AS has_health_access,
    CASE
        WHEN source.seg_soc IN ('1', '2') THEN 'observed'
        WHEN source.seg_soc = '3' THEN 'unspecified'
        WHEN source.seg_soc IS NULL THEN 'missing'
        ELSE NULL
    END AS health_access_state,
    CASE source.pre_asa
        WHEN '1' THEN true
        WHEN '2' THEN false
        ELSE NULL
    END AS has_other_benefits,
    CASE
        WHEN source.pre_asa IN ('1', '2') THEN 'observed'
        WHEN source.pre_asa = '3' THEN 'unspecified'
        WHEN source.pre_asa IS NULL THEN 'missing'
        ELSE NULL
    END AS other_benefits_state,
    CASE
        WHEN source.tip_con IN ('1', '2', '3', '4') THEN true
        WHEN source.tip_con = '5' THEN false
        ELSE NULL
    END AS has_written_contract,
    CASE source.tip_con
        WHEN '2' THEN 'temporary'
        WHEN '3' THEN 'indefinite'
        ELSE NULL
    END AS contract_type,
    CASE
        WHEN source.tip_con IN ('2', '3') THEN 'observed_type'
        WHEN source.tip_con IN ('1', '4') THEN 'type_unspecified'
        WHEN source.tip_con = '5' THEN 'not_applicable'
        WHEN source.tip_con = '6' THEN 'unspecified'
        WHEN source.tip_con IS NULL THEN 'missing'
        ELSE NULL
    END AS contract_type_state,
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
