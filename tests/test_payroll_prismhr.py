"""PrismHR payroll adapter."""
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import prismhr

COMPANY = "prismhr:132"


class PrismHRPayrollChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("prismhr", "payroll")
        cls.output = prismhr.normalize_payroll(cls.bundle).to_dict()

    def pay_run(self, batch_id):
        return next(r for r in self.output["pay_runs"] if r["source"]["pay_run_id"] == batch_id)

    def check(self, voucher_id):
        return next(c for c in self.output["paychecks"] if c["source"]["paycheck_id"] == voucher_id)

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("prismhr", "payroll"))

    def test_is_deterministic(self):
        self.assertEqual(prismhr.normalize_payroll(self.bundle).to_dict(), self.output)

    def test_records_link_to_runs_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("prismhr")["employees"]}
        self.assertEqual(len(self.output["pay_runs"]), 1)
        self.assertEqual(len(self.output["paychecks"]), 8)
        run_key = f"{COMPANY}:run:202601"
        for check in self.output["paychecks"]:
            with self.subTest(key=check["key"]):
                self.assertIn(check["employee_key"], employee_keys)
                self.assertEqual(check["company_key"], COMPANY)
                self.assertEqual(check["pay_run_key"], run_key)
                self.assertTrue(check["key"].startswith(check["employee_key"] + ":chk:"))

    def test_batch_fields(self):
        run = self.pay_run("202601")
        self.assertEqual(run["pay_date"], "2026-01-09")
        self.assertEqual(run["period"], {"start": "2025-12-27", "end": "2026-01-02"})
        self.assertEqual(run["status"]["value"], "completed")
        self.assertEqual(run["type"]["value"], "regular")

    def test_printed_status_is_reported_once(self):
        first = self.check("V100001")
        self.assertEqual(first["gross_pay"], {"amount": "1000.0", "currency": "USD"})
        self.assertEqual(first["net_pay"], {"amount": "920.0", "currency": "USD"})
        self.assertEqual(first["status"]["value"], "unknown")
        found = issues_with(self.output, "undocumented_code", "status")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(first["key"], "PRNT")])

    def test_code_tables_quote_the_spec_descriptions(self):
        status = resolve_code_table(prismhr.BATCH_STATUS)
        for code, label in prismhr.BATCH_STATUS_LABELS.items():
            with self.subTest(code=code):
                self.assertIn(f"<td>{code}</td>", status)
                self.assertIn(f"<td>{label}</td>", status)
        self.assertEqual(sorted(prismhr.BATCH_STATUS.entries), sorted(prismhr.BATCH_STATUS_LABELS))
        for code in prismhr.BATCH_TYPE.entries:
            self.assertIn(f"({code})", resolve_code_table(prismhr.BATCH_TYPE))
        for table in (prismhr.VOUCHER_TYPE, prismhr.PAY_CLASS):
            for code in table.entries:
                with self.subTest(table=table.name, code=code):
                    self.assertIn(f"'{code}'", resolve_code_table(table))


if __name__ == "__main__":
    unittest.main()
