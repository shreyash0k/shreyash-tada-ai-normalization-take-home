"""UKG Ready payroll adapter."""
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import ukg_ready

COMPANY = "ukg-ready:33704016"
IDS = [str(12935181566 + i) for i in range(8)]


class UkgReadyPayrollChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("ukg-ready", "payroll")
        cls.output = ukg_ready.normalize_payroll(cls.bundle).to_dict()

    def pay_run(self, payroll_id):
        return next(r for r in self.output["pay_runs"] if r["source"]["pay_run_id"] == payroll_id)

    def check(self, statement_id):
        return next(c for c in self.output["paychecks"] if c["source"]["paycheck_id"] == statement_id)

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("ukg-ready", "payroll"))

    def test_is_deterministic(self):
        self.assertEqual(ukg_ready.normalize_payroll(self.bundle).to_dict(), self.output)

    def test_records_link_to_runs_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("ukg-ready")["employees"]}
        self.assertEqual(len(self.output["pay_runs"]), 1)
        self.assertEqual(len(self.output["paychecks"]), 8)
        for index, check in enumerate(self.output["paychecks"]):
            with self.subTest(key=check["key"]):
                self.assertEqual(check["employee_key"], f"{COMPANY}:{IDS[index]}")
                self.assertIn(check["employee_key"], employee_keys)
                self.assertEqual(check["company_key"], COMPANY)
                self.assertEqual(check["pay_run_key"], f"{COMPANY}:run:4332470001")

    def test_payroll_fields(self):
        run = self.pay_run("4332470001")
        self.assertEqual(run["description"], "Primary-EIN Regular Bi-Weekly 01/09/2026")
        self.assertEqual(run["pay_date"], "2026-01-09")
        self.assertEqual(run["period"], {"start": "2025-12-21", "end": "2026-01-03"})
        self.assertEqual(run["status"]["value"], "completed")

    def test_gross_up_type_stays_raw(self):
        gross_up = self.check("85950008")
        self.assertEqual(gross_up["type"]["label"], "Gross Up")
        self.assertEqual(gross_up["type"]["value"], "unknown")
        found = issues_with(self.output, "unmapped_label", "type.display_name")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(gross_up["key"], "Gross Up")])

    def test_no_totals_and_live_only_fields(self):
        self.assertEqual({(c["gross_pay"], c["net_pay"], c["check_number"]) for c in self.output["paychecks"]},
                         {(None, None, None)})
        live = issues_with(self.output, "spec_live_mismatch")
        self.assertEqual([i["source_path"] for i in live],
                         ["pay_statements[0].calcUpto", "pay_statements[0].emptyEarning"])

    def test_status_tables_cover_the_schema_enums_exactly(self):
        for table in (ukg_ready.PAYROLL_STATUS, ukg_ready.STATEMENT_STATUS):
            with self.subTest(table=table.name):
                self.assertEqual(sorted(table.entries), sorted(resolve_code_table(table)))
        for table in (ukg_ready.PAYROLL_TYPE, ukg_ready.STATEMENT_TYPE, ukg_ready.PAYMENT_TYPE):
            with self.subTest(table=table.name):
                self.assertEqual(table.kind, "label")
                self.assertIn("type", resolve_code_table(table))


if __name__ == "__main__":
    unittest.main()
