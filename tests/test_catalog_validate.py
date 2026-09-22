"""Behavioral tests for database-catalog coverage validation."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scripts.catalog_validate import CatalogError, validate_catalog, validate_payload


class CatalogValidationTests(unittest.TestCase):
    def test_complete_coverage_is_accepted(self):
        self.assertEqual(
            validate_payload({"missing": [], "extra": []}),
            {"catalog_coverage": "complete", "objects": 3},
        )

    def test_missing_physical_column_fails_closed(self):
        with self.assertRaisesRegex(CatalogError, "catalog coverage drift"):
            validate_payload(
                {
                    "missing": [
                        {
                            "schema_name": "analysis",
                            "object_name": "enoe_person_quarter_prepared",
                            "column_name": "new_field",
                        }
                    ],
                    "extra": [],
                }
            )

    def test_stale_catalog_column_fails_closed(self):
        with self.assertRaisesRegex(CatalogError, "catalog coverage drift"):
            validate_payload(
                {
                    "missing": [],
                    "extra": [
                        {
                            "schema_name": "staging",
                            "object_name": "enoe_person_quarter",
                            "column_name": "removed_field",
                        }
                    ],
                }
            )

    def test_database_validation_parses_aggregate_only_evidence(self):
        with patch(
            "scripts.catalog_validate.database_sql",
            return_value=json.dumps({"missing": [], "extra": []}),
        ):
            self.assertEqual(validate_catalog()["catalog_coverage"], "complete")


if __name__ == "__main__":
    unittest.main()
