"""isolved payroll adapter."""
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import isolved

COMPANY = "isolved:4046-5806"


class IsolvedPayrollChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("isolved", "payroll")
        cls.output = isolved.normalize_payroll(cls.bundle).to_dict()

    def pay_run(self, run_id):
        return next(r for r in self.output["pay_runs"] if r["source"]["pay_run_id"] == run_id)

    def check(self, check_id):
        return next(c for c in self.output["paychecks"] if c["source"]["paycheck_id"] == check_id)

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("isolved", "payroll"))

    def test_is_deterministic(self):
        self.assertEqual(isolved.normalize_payroll(self.bundle).to_dict(), self.output)

    def test_records_link_to_runs_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("isolved")["employees"]}
        self.assertEqual(len(self.output["pay_runs"]), 1)
        self.assertEqual(len(self.output["paychecks"]), 8)
        for check in self.output["paychecks"]:
            with self.subTest(key=check["key"]):
                self.assertIn(check["employee_key"], employee_keys)
                self.assertEqual(check["company_key"], COMPANY)
                self.assertEqual(check["pay_run_key"], f"{COMPANY}:run:4100001")

    def test_run_fields(self):
        run = self.pay_run("4100001")
        self.assertEqual(run["pay_date"], "2026-01-09")
        self.assertEqual(run["period"], {"start": "2025-12-22", "end": "2026-01-04"})
        self.assertEqual(run["type"]["value"], "regular")
        self.assertEqual(run["status"]["value"], "completed")

    def test_one_check_has_no_detail(self):
        missing = self.check("21010008")
        self.assertEqual(missing["gross_pay"], {"amount": "1000.0", "currency": "USD"})
        self.assertEqual(missing["taxes"], [])
        found = issues_with(self.output, "missing_section", "check_detail")
        self.assertEqual([i["record_key"] for i in found], [missing["key"]])

    def test_allowlists_cite_the_spec_fields(self):
        for table in (isolved.RUN_TYPE, isolved.RUN_STATUS, isolved.CHECK_TYPE):
            with self.subTest(table=table.name):
                self.assertEqual(table.kind, "label")
                self.assertIn(resolve_code_table(table)["description"], table.evidence)


if __name__ == "__main__":
    unittest.main()
