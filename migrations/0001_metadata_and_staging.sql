-- The migration runner records this file and its SHA-256 in metadata.schema_migrations.
CREATE SCHEMA IF NOT EXISTS metadata;
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS metadata.schema_migrations (
    version text PRIMARY KEY,
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at_utc timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metadata.source_archives (
    archive_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name text NOT NULL,
    survey_year integer NOT NULL CHECK (survey_year BETWEEN 2005 AND 2100),
    survey_quarter smallint NOT NULL CHECK (survey_quarter BETWEEN 1 AND 4),
    download_url text NOT NULL,
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    source_published_at_utc timestamptz,
    recorded_at_utc timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_name, survey_year, survey_quarter, content_sha256)
);

CREATE TABLE IF NOT EXISTS metadata.ingestion_runs (
    ingestion_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    archive_id bigint REFERENCES metadata.source_archives (archive_id),
    pipeline_revision text NOT NULL,
    started_at_utc timestamptz NOT NULL DEFAULT now(),
    completed_at_utc timestamptz,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (
        (status = 'running' AND completed_at_utc IS NULL)
        OR (status IN ('succeeded', 'failed') AND completed_at_utc IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS source_archives_period_idx
    ON metadata.source_archives (survey_year, survey_quarter);
CREATE INDEX IF NOT EXISTS ingestion_runs_archive_idx
    ON metadata.ingestion_runs (archive_id);
