"""Test connection isolation and fail-closed aggregate extraction."""

import subprocess
import unittest
from unittest.mock import patch

from scripts.audit_source import command, run_query


class AuditRunnerTests(unittest.TestCase):
    def test_database_is_positional_not_shell_code(self):
        database = "name; $(touch unwanted)"
        args = command({"ENOE_DOCKER_CONTAINER": "postgres-dev", "PGDATABASE": database})
        self.assertEqual(args[-1], database)
        self.assertNotIn(database, args[-3])
        self.assertIn("-X", args[-3])

    @patch("scripts.audit_source.subprocess.run")
    def test_read_only_snapshot_and_timeout(self, execute):
        execute.return_value.stdout = '{"records": 3}'
        result = run_query("SELECT 1;", {})
        self.assertEqual(result["records"], 3)
        kwargs = execute.call_args.kwargs
        self.assertTrue(
            kwargs["input"].startswith("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;")
        )
        self.assertIn("statement_timeout", kwargs["input"])
        self.assertTrue(kwargs["check"])
        self.assertEqual(kwargs["timeout"], 180)

    @patch("scripts.audit_source.subprocess.run")
    def test_query_failure_is_not_accepted_as_evidence(self, execute):
        execute.side_effect = subprocess.CalledProcessError(1, "psql")
        with self.assertRaises(subprocess.CalledProcessError):
            run_query("SELECT 1;", {})


if __name__ == "__main__":
    unittest.main()
