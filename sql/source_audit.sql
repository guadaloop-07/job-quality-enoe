-- All outputs are aggregates. No person or household identifiers are exported.
WITH source AS MATERIALIZED (
    SELECT * FROM public.stg_enoe_microdatos
    WHERE anio BETWEEN 2023 AND 2026
      AND (anio < 2026 OR trimestre <= 2)
), stages AS (
    SELECT *, CASE
        WHEN entidad_id IS DISTINCT FROM 14 THEN 0
        WHEN r_def IS DISTINCT FROM 0 THEN 1
        WHEN c_res IS NULL OR c_res NOT IN (1, 3) THEN 2
        WHEN eda IS NULL OR eda NOT BETWEEN 15 AND 98 THEN 3
        WHEN clase2 IS DISTINCT FROM 1 THEN 4
        WHEN situacion_trabajo_id IS DISTINCT FROM 1 THEN 5
        ELSE 6 END AS passed
    FROM source
), expected AS (
    SELECT y AS anio, q AS trimestre
    FROM generate_series(2023, 2026) y CROSS JOIN generate_series(1, 4) q
    WHERE y < 2026 OR q <= 2
), funnel AS (
    SELECT e.anio, e.trimestre, step,
        count(s.anio) AS records,
        coalesce(sum(s.fac) FILTER (WHERE s.fac > 0), 0) AS valid_weight_sum,
        count(s.anio) FILTER (WHERE s.fac IS NULL OR s.fac <= 0) AS invalid_weights
    FROM expected e CROSS JOIN generate_series(0, 6) step
    LEFT JOIN stages s ON s.anio = e.anio AND s.trimestre = e.trimestre
        AND s.passed >= step
    GROUP BY e.anio, e.trimestre, step
), candidate AS MATERIALIZED (
    SELECT * FROM stages WHERE passed = 6
), codes AS (
    SELECT anio, trimestre, variable, value, count(*) AS records,
        coalesce(sum(fac) FILTER (WHERE fac > 0), 0) AS valid_weight_sum
    FROM candidate CROSS JOIN LATERAL (VALUES
        ('seg_soc', seg_soc), ('medica5c', medica5c), ('pre_asa', pre_asa),
        ('tip_con', tip_con), ('p3i', p3i), ('tue_ppal', tue_ppal),
        ('emp_ppal', emp_ppal)
    ) v(variable, value)
    GROUP BY anio, trimestre, variable, value
), numeric_profile AS (
    SELECT anio, trimestre, variable, count(*) AS records,
        count(*) FILTER (WHERE value IS NULL) AS null_records,
        count(*) FILTER (WHERE value = 0) AS zero_records,
        count(*) FILTER (WHERE value < 0) AS negative_records,
        coalesce(sum(fac) FILTER (WHERE fac > 0), 0) AS valid_weight_sum,
        coalesce(sum(fac) FILTER (WHERE fac > 0 AND value IS NULL), 0) AS null_weight,
        coalesce(sum(fac) FILTER (WHERE fac > 0 AND value = 0), 0) AS zero_weight,
        min(value) AS minimum, max(value) AS maximum,
        percentile_cont(ARRAY[0.25, 0.5, 0.75, 0.99])
            WITHIN GROUP (ORDER BY value) AS unweighted_raw_quantiles
    FROM candidate CROSS JOIN LATERAL (VALUES
        ('ingocup', ingocup), ('hrsocup', hrsocup)
    ) v(variable, value)
    GROUP BY anio, trimestre, variable
), semantic_consistency AS (
    SELECT anio, trimestre, count(*) AS records,
        count(*) FILTER (WHERE ingocup = 0 AND ing7c BETWEEN 1 AND 5)
            AS income_zero_bracket_records,
        coalesce(sum(fac) FILTER (WHERE fac > 0 AND ingocup = 0
            AND ing7c BETWEEN 1 AND 5), 0) AS income_zero_bracket_weight,
        count(*) FILTER (WHERE ingocup = 0 AND ing7c = 6)
            AS income_zero_no_income_records,
        coalesce(sum(fac) FILTER (WHERE fac > 0 AND ingocup = 0 AND ing7c = 6), 0)
            AS income_zero_no_income_weight,
        count(*) FILTER (WHERE ingocup = 0 AND ing7c = 7)
            AS income_zero_unspecified_records,
        coalesce(sum(fac) FILTER (WHERE fac > 0 AND ingocup = 0 AND ing7c = 7), 0)
            AS income_zero_unspecified_weight,
        count(*) FILTER (WHERE ingocup > 0 AND (ing7c IS NULL OR ing7c IN (6, 7)))
            AS income_positive_category_conflicts,
        count(*) FILTER (WHERE hrsocup = 0 AND dur9c = 1) AS hours_zero_absent_records,
        count(*) FILTER (WHERE hrsocup = 0 AND dur9c = 9)
            AS hours_zero_unspecified_records,
        count(*) FILTER (WHERE hrsocup = 0 AND (dur9c IS NULL OR dur9c NOT IN (1, 9)))
            AS hours_zero_other_records
    FROM candidate GROUP BY anio, trimestre
), design AS (
    SELECT anio, trimestre, count(*) AS records,
        count(*) FILTER (WHERE est_d_tri IS NULL) AS null_strata,
        count(*) FILTER (WHERE upm IS NULL) AS null_upm,
        count(*) FILTER (WHERE est_d_tri <= 0 OR upm <= 0) AS nonpositive_design,
        count(DISTINCT est_d_tri) AS strata,
        count(DISTINCT (est_d_tri, upm)) AS stratum_upm_pairs,
        count(*) FILTER (WHERE (tue_ppal = 1) IS DISTINCT FROM (emp_ppal = 1))
            AS informal_predicate_disagreements,
        count(*) FILTER (WHERE tue_ppal IS NULL OR emp_ppal IS NULL)
            AS incomplete_informal_comparison
    FROM candidate GROUP BY anio, trimestre
), keys AS (
    SELECT anio, trimestre, cd_a, entidad_id, con, v_sel, n_hog, h_mud,
        n_ent, n_ren, count(*) AS n
    FROM source GROUP BY anio, trimestre, cd_a, entidad_id, con, v_sel,
        n_hog, h_mud, n_ent, n_ren
), integrity AS (
    SELECT anio, trimestre, sum(n) AS records,
        count(*) FILTER (WHERE n > 1) AS duplicate_keys,
        coalesce(sum(n - 1) FILTER (WHERE n > 1), 0) AS excess_records,
        coalesce(sum(n) FILTER (WHERE cd_a IS NULL OR entidad_id IS NULL
            OR con IS NULL OR v_sel IS NULL OR n_hog IS NULL OR h_mud IS NULL
            OR n_ent IS NULL OR n_ren IS NULL), 0) AS null_key_records
    FROM keys GROUP BY anio, trimestre
)
SELECT json_build_object(
    'database', current_database(),
    'server_version', current_setting('server_version'),
    'read_only', current_setting('transaction_read_only'),
    'snapshot', pg_current_snapshot()::text,
    'columns', (SELECT json_agg(c ORDER BY ordinal_position) FROM (
        SELECT column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'stg_enoe_microdatos'
    ) c),
    'relations', (SELECT json_agg(r ORDER BY relname) FROM (
        SELECT c.relname, c.relkind FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm', 'f')
    ) r),
    'funnel', (SELECT json_agg(f ORDER BY anio, trimestre, step) FROM funnel f),
    'codes', (SELECT json_agg(c ORDER BY anio, trimestre, variable, value) FROM codes c),
    'numeric', (SELECT json_agg(n ORDER BY anio, trimestre, variable) FROM numeric_profile n),
    'semantic_consistency',
        (SELECT json_agg(s ORDER BY anio, trimestre) FROM semantic_consistency s),
    'design', (SELECT json_agg(d ORDER BY anio, trimestre) FROM design d),
    'integrity', (SELECT json_agg(i ORDER BY anio, trimestre) FROM integrity i)
);
