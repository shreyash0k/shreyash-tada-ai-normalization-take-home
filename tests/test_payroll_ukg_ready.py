"""UKG Ready payroll adapter: golden output plus the injected edge cases."""
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import ukg_ready

COMPANY = "ukg-ready:33704016"
IDS = [str(12935181566 + i) for i in range(6)]


def money(amount):
    return {"amount": amount, "currency": "USD"}


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
        self.assertEqual(len(self.output["pay_runs"]), 4)
        self.assertEqual([c["source"]["paycheck_id"] for c in self.output["paychecks"]],
                         ["85940001", "85940002", "85940003", "85940004", "85940005"])
        for index, check in enumerate(self.output["paychecks"]):
            with self.subTest(key=check["key"]):
                self.assertEqual(check["employee_key"], f"{COMPANY}:{IDS[index]}")
                self.assertIn(check["employee_key"], employee_keys)
                self.assertEqual(check["company_key"], COMPANY)
        self.assertEqual(self.check("85940001")["pay_run_key"], f"{COMPANY}:run:4332470001")
        self.assertEqual(self.check("85940004")["pay_run_key"], f"{COMPANY}:run:4332470002")

    def test_payroll_fields(self):
        run = self.pay_run("4332470001")
        self.assertEqual(run["type"], {"raw": "641", "label": "Regular", "value": "regular"})
        self.assertEqual(run["status"], {"raw": "FINALIZED", "label": None, "value": "completed"})
        self.assertEqual((run["pay_date"], run["period"]), ("2026-01-09", {"start": "2025-12-21", "end": "2026-01-03"}))
        self.assertEqual(run["description"], "Primary-EIN Regular Bi-Weekly 01/09/2026")
        self.assertEqual(run["pay_group"], {"raw": "35419520", "label": "Primary EIN", "value": None})
        self.assertEqual(run["unmapped"]["payrolls[0].ein.ein_tax_id"], "12-3456789")

    def test_payroll_statuses_and_types(self):
        self.assertEqual([r["status"]["value"] for r in self.output["pay_runs"]],
                         ["completed", "open", "unknown", "failed"])
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "out_of_schema_value")], ["PAUSED"])
        self.assertEqual(self.pay_run("4332470002")["type"], {"raw": "706", "label": "Correction", "value": "unknown"})
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "unmapped_label")],
                         ["Correction", "Gross Up", "Pay Card"])

    def test_statement_lines(self):
        check = self.check("85940001")
        self.assertEqual(check["status"], {"raw": "FINALIZED", "label": None, "value": "finalized"})
        self.assertEqual(check["type"], {"raw": "36656000", "label": "Regular", "value": "regular"})
        self.assertEqual([(e["code"]["raw"], e["hours"], e["rate"], e["amount"]) for e in check["earnings"]],
                         [("REG", "80.00", money("25.0"), money("2000.0")), ("OT", "2.00", money("37.5"), money("75.0"))])
        self.assertEqual([(t["code"]["raw"], t["employee_amount"], t["employer_amount"], t["employee_taxable_wages"])
                          for t in check["taxes"]],
                         [("FIT", money("210.0"), money("0.0"), money("1954.5")),
                          ("SS", money("128.65"), money("128.65"), money("2075.0"))])
        self.assertEqual([(p["method"]["value"], p["amount"]) for p in check["payments"]],
                         [("direct_deposit", money("1500.0")), ("check", money("40.85"))])
        self.assertEqual(check["unmapped"]["pay_statements[0].messages[0].message.text"], "Synthetic note")

    def test_deductions_split_by_side(self):
        check = self.check("85940001")
        self.assertEqual([(d["code"]["raw"], d["amount"]) for d in check["deductions"]],
                         [("401k", money("120.0")), ("S125_Med", money("45.5")), ("401K Loan 1", money("30.0"))])
        self.assertEqual([(c["code"]["raw"], c["amount"]) for c in check["employer_contributions"]],
                         [("401k", money("60.0")), ("ER_HSA", money("25.0"))])
        self.assertEqual(check["deductions"][0]["unmapped"], check["employer_contributions"][0]["unmapped"])
        self.assertEqual(check["deductions"][1]["unmapped"]["pay_statements[0].deductions[1].er_amount"], 0.0)
        self.assertEqual(check["deductions"][2]["unmapped"]["pay_statements[0].deductions[3].type_name"],
                         "Deduction (Discarded)")

    def test_no_totals_and_live_only_fields(self):
        self.assertEqual({(c["gross_pay"], c["net_pay"], c["check_number"]) for c in self.output["paychecks"]},
                         {(None, None, None)})
        totals = issues_with(self.output, "missing_section", "pay_statement_detail")
        self.assertEqual([(i["record_key"], i["action"]) for i in totals if i["record_key"] is None],
                         [(None, "gross_pay and net_pay set null")])
        live = issues_with(self.output, "spec_live_mismatch")
        self.assertEqual([i["source_path"] for i in live],
                         ["pay_statements[0].calcUpto", "pay_statements[0].emptyEarning"])

    def test_hours_that_are_not_milliseconds(self):
        earning = self.check("85940002")["earnings"][0]
        self.assertIsNone(earning["hours"])
        self.assertEqual(earning["amount"], money("160.0"))
        found = issues_with(self.output, "invalid_number")
        self.assertEqual([(i["source_path"], i["raw_value"]) for i in found],
                         [("pay_statements[1].earnings[0].hours", "eight hours")])
        self.assertEqual(self.check("85940005")["earnings"][0]["hours"], "40.00")

    def test_statements_without_detail_or_listed_payroll(self):
        bare = self.check("85940003")
        self.assertEqual((bare["status"]["value"], bare["earnings"], bare["payments"]), ("closed", [], []))
        missing = [i for i in issues_with(self.output, "missing_section", "pay_statement_detail") if i["record_key"]]
        self.assertEqual([(i["record_key"], i["severity"]) for i in missing], [(bare["key"], "warning")])
        self.assertEqual(self.check("85940004")["status"]["value"], "invalid")
        orphan = self.check("85940005")
        self.assertIsNone(orphan["pay_run_key"])
        self.assertEqual(orphan["source"]["pay_run_id"], "4332479999")
        unlisted = issues_with(self.output, "missing_section", "pay_statements['4332479999']")
        self.assertEqual([(i["record_key"], i["severity"]) for i in unlisted], [(orphan["key"], "warning")])
        no_entry = [i for i in issues_with(self.output, "missing_section") if i["source_path"] == "pay_statements"]
        self.assertEqual([(i["record_key"], i["severity"]) for i in no_entry], [(f"{COMPANY}:run:4332470003", "info")])

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
