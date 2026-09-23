#!/usr/bin/env python3
"""Validate that user-facing ENOE objects and their catalog entries agree."""

from __future__ import annotations

import json

if __package__:
    from scripts.enoe_ingest import database_sql
else:
    from enoe_ingest import database_sql


class CatalogError(ValueError):
    """Raised when the database catalog and physical schema diverge."""


CATALOG_VALIDATION_SQL = """
WITH physical AS (
    SELECT table_schema AS schema_name, table_name AS object_name, column_name
    FROM information_schema.columns
    WHERE (table_schema, table_name) IN (
        ('staging', 'enoe_person_quarter'),
        ('analysis', 'enoe_person_quarter_prepared'),
        ('analysis', 'enoe_weighted_profile')
    )
), cataloged AS (
    SELECT objects.schema_name, objects.object_name, columns.column_name
    FROM metadata.catalog_columns AS columns
    JOIN metadata.catalog_tables AS objects
        ON objects.catalog_table_id = columns.catalog_table_id
    WHERE objects.is_user_facing
      AND (objects.schema_name, objects.object_name) IN (SELECT schema_name, object_name FROM physical)
), missing AS (
    SELECT * FROM physical EXCEPT SELECT * FROM cataloged
), extra AS (
    SELECT * FROM cataloged EXCEPT SELECT * FROM physical
)
SELECT json_build_object(
    'missing', coalesce((SELECT json_agg(row_to_json(missing)) FROM missing), '[]'::json),
    'extra', coalesce((SELECT json_agg(row_to_json(extra)) FROM extra), '[]'::json)
)::text;
"""


def validate_payload(payload: dict[str, object]) -> dict[str, object]:
    """Reject incomplete or stale catalog coverage without exposing survey rows."""
    missing = payload.get("missing")
    extra = payload.get("extra")
    if not isinstance(missing, list) or not isinstance(extra, list):
        raise CatalogError("catalog validation returned an invalid structure")
    if missing or extra:
        raise CatalogError(f"catalog coverage drift: missing={missing!r}; extra={extra!r}")
    return {"catalog_coverage": "complete", "objects": 3}


def validate_catalog() -> dict[str, object]:
    """Query catalog coverage and return aggregate-only validation evidence."""
    try:
        payload = json.loads(database_sql(CATALOG_VALIDATION_SQL))
    except json.JSONDecodeError as error:
        raise CatalogError("catalog validation did not return JSON") from error
    if not isinstance(payload, dict):
        raise CatalogError("catalog validation returned an invalid structure")
    return validate_payload(payload)


def main() -> None:
    print(json.dumps(validate_catalog(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
