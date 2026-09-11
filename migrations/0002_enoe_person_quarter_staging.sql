ALTER TABLE metadata.source_archives
    ADD COLUMN IF NOT EXISTS archive_name text,
    ADD COLUMN IF NOT EXISTS byte_size bigint CHECK (byte_size > 0),
    ADD COLUMN IF NOT EXISTS retrieved_at_utc timestamptz;

CREATE TABLE IF NOT EXISTS staging.enoe_person_quarter (
    survey_year integer NOT NULL CHECK (survey_year BETWEEN 2005 AND 2100),
    survey_quarter smallint NOT NULL CHECK (survey_quarter BETWEEN 1 AND 4),
    tipo text NOT NULL,
    mes_cal text NOT NULL,
    cd_a text NOT NULL,
    entity integer NOT NULL,
    con text NOT NULL,
    v_sel text NOT NULL,
    n_hog text NOT NULL,
    h_mud text NOT NULL,
    n_ren text NOT NULL,
    r_def text,
    c_res text,
    eda text,
    clase2 text,
    pos_ocu text,
    fac_tri numeric(18, 6) NOT NULL CHECK (fac_tri > 0),
    est_d_tri text,
    upm text,
    remune2c text,
    ingocup text,
    ing7c text,
    hrsocup text,
    dur9c text,
    tip_con text,
    seg_soc text,
    pre_asa text,
    medica5c text,
    tue_ppal text,
    emp_ppal text,
    p3i text,
    source_archive_sha256 text NOT NULL CHECK (source_archive_sha256 ~ '^[0-9a-f]{64}$'),
    loaded_at_utc timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (
        survey_year,
        survey_quarter,
        tipo,
        mes_cal,
        cd_a,
        entity,
        con,
        v_sel,
        n_hog,
        h_mud,
        n_ren
    )
);

CREATE INDEX IF NOT EXISTS enoe_person_quarter_period_idx
    ON staging.enoe_person_quarter (survey_year, survey_quarter);
