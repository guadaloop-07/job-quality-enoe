"""Execute the actual SQL on synthetic CTEs without writing any database objects."""

import os
import unittest

from scripts.audit_source import ROOT, run_query


@unittest.skipUnless(os.environ.get("ENOE_TEST_POSTGRES") == "1", "PostgreSQL opt-in required")
class AuditSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = dict(
            anio=2023,
            trimestre=1,
            entidad_id=14,
            r_def=0,
            c_res=1,
            eda=35,
            clase2=1,
            situacion_trabajo_id=1,
            fac=100,
            seg_soc=1,
            medica5c=1,
            pre_asa=1,
            tip_con=1,
            p3i=1,
            tue_ppal=1,
            emp_ppal=2,
            ingocup=0,
            ing7c=2,
            hrsocup=40,
            dur9c=6,
            est_d_tri=1,
            upm=1,
            cd_a=2,
            con=1,
            v_sel=1,
            n_hog=1,
            h_mud=0,
            n_ent=1,
            n_ren=1,
        )
        rows = [base, base.copy()]
        rows += [dict(base, n_ren=2, fac=-1, p3i=None, ingocup=None)]
        # Each failure is excluded at exactly its corresponding funnel step.
        for i, (field, value) in enumerate(
            [
                ("entidad_id", 13),
                ("r_def", None),
                ("c_res", 2),
                ("eda", 99),
                ("clase2", 2),
                ("situacion_trabajo_id", 3),
            ],
            3,
        ):
            rows.append(dict(base, n_ren=i, **{field: value}))
        # Outside the approved audit window; must never enter its totals.
        rows.append(dict(base, anio=2026, trimestre=3))
        values = ",".join(
            "(" + ",".join("NULL" if v is None else str(v) for v in row.values()) + ")"
            for row in rows
        )
        fixture = "(VALUES " + values + ") AS fixture(" + ",".join(base) + ")"
        sql = (ROOT / "sql" / "source_audit.sql").read_text()
        cls.result = run_query(sql.replace("FROM public.stg_enoe_microdatos", "FROM " + fixture))

    def test_funnel_and_invalid_weight_denominator(self):
        rows = [r for r in self.result["funnel"] if (r["anio"], r["trimestre"]) == (2023, 1)]
        self.assertEqual([r["records"] for r in rows], [9, 8, 7, 6, 5, 4, 3])
        self.assertEqual(rows[-1]["valid_weight_sum"], 200)
        self.assertEqual(rows[-1]["invalid_weights"], 1)
        self.assertEqual(self.result["read_only"], "on")

    def test_missing_quarters_are_explicit(self):
        self.assertEqual(len(self.result["funnel"]), 14 * 7)
        missing = [r for r in self.result["funnel"] if r["anio"] == 2026]
        self.assertTrue(all(r["records"] == 0 and r["invalid_weights"] == 0 for r in missing))

    def test_duplicate_keys_and_null_codes_remain_visible(self):
        self.assertEqual(self.result["integrity"][0]["duplicate_keys"], 1)
        self.assertEqual(self.result["integrity"][0]["excess_records"], 1)
        nulls = [r for r in self.result["codes"] if r["variable"] == "p3i" and r["value"] is None]
        self.assertEqual(nulls[0]["records"], 1)
        self.assertEqual(nulls[0]["valid_weight_sum"], 0)
        income = next(r for r in self.result["numeric"] if r["variable"] == "ingocup")
        self.assertEqual(income["null_records"], 1)
        self.assertEqual(income["zero_records"], 2)
        self.assertEqual(income["zero_weight"], 200)
        semantics = next(
            r
            for r in self.result["semantic_consistency"]
            if (r["anio"], r["trimestre"]) == (2023, 1)
        )
        self.assertEqual(semantics["income_zero_bracket_records"], 2)
        self.assertEqual(semantics["income_zero_bracket_weight"], 200)
        self.assertEqual(semantics["income_zero_unspecified_records"], 0)
