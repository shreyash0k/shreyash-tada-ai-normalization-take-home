"""PrismHR payroll adapter: golden output plus the injected edge cases."""
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, raw_bundle, resolve_code_table
from normalization.adapters import prismhr

IDS = raw_bundle("prismhr")["responses"]["get_employee_list"]["employeeList"]["employeeId"]
COMPANY = "prismhr:132"


def money(amount):
    return {"amount": amount, "currency": "USD"}


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
        run_keys = {r["key"] for r in self.output["pay_runs"]}
        self.assertEqual(len(run_keys), 5)
        self.assertEqual([c["source"]["paycheck_id"] for c in self.output["paychecks"]],
                         ["V000101", "V000102", "V000103", "V000201", "V000901"])
        for check in self.output["paychecks"]:
            with self.subTest(key=check["key"]):
                self.assertIn(check["employee_key"], employee_keys)
                self.assertEqual(check["company_key"], COMPANY)
                self.assertTrue(check["key"].startswith(check["employee_key"] + ":chk:"))
                if check["source"]["paycheck_id"] != "V000901":
                    self.assertIn(check["pay_run_key"], run_keys)
        self.assertEqual(self.check("V000101")["pay_run_key"], f"{COMPANY}:run:202601")

    def test_batch_fields_and_batch_info(self):
        run = self.pay_run("202601")
        self.assertEqual(run["type"], {"raw": "R", "label": "Regular", "value": "regular"})
        self.assertEqual(run["status"], {"raw": "COMP", "label": "Payroll is complete", "value": "completed"})
        self.assertEqual(run["pay_date"], "2026-01-09")
        self.assertEqual(run["period"], {"start": "2025-12-27", "end": "2026-01-02"})
        self.assertEqual(run["pay_group"], {"raw": "WFRI", "label": None, "value": None})
        self.assertEqual(run["description"], "202601 - 01-09-26 WFRI")
        self.assertEqual(run["unmapped"]["batchList[0].payGroup[0].weeksWorked"], 1)
        self.assertEqual(run["unmapped"]["batchControl.processor"], "synthetic")
        self.assertNotIn("batchControl.batchId", run["unmapped"])
        self.assertIsNone(self.pay_run("202602")["description"])

    def test_batch_types_and_status_groups(self):
        runs = self.output["pay_runs"]
        self.assertEqual([r["type"]["value"] for r in runs], ["regular", "regular", "manual", "special", "void"])
        self.assertEqual([r["status"]["value"] for r in runs], ["completed", "submitted", "failed", "open", "unknown"])

    def test_pay_group_count_decides_the_period(self):
        two = self.pay_run("202604")
        self.assertIsNone(two["period"])
        self.assertIsNone(two["pay_group"])
        self.assertEqual(two["unmapped"]["batchList[3].payGroup[1].payGroupId"], "SEMI")
        found = issues_with(self.output, "inconsistent_allocation")
        self.assertEqual([i["record_key"] for i in found], [two["key"]])
        self.assertIsNone(self.pay_run("202603")["period"])
        self.assertNotIn("batchList[2].payGroup", self.pay_run("202603")["unmapped"])
        blank = self.pay_run("202605")
        self.assertIsNone(blank["pay_group"])
        self.assertEqual(blank["period"], {"start": "2026-01-17", "end": "2026-01-23"})

    def test_regular_voucher_lines(self):
        check = self.check("V000101")
        self.assertEqual(check["type"], {"raw": "R", "label": "Regular", "value": "regular"})
        self.assertEqual((check["gross_pay"], check["net_pay"]), (money("1076.41"), money("891.38")))
        self.assertEqual(check["check_number"], "1001")
        self.assertEqual(check["period"], {"start": "2025-12-27", "end": "2026-01-02"})
        earnings = check["earnings"]
        self.assertEqual([(e["code"]["raw"], e["hours"], e["rate"], e["amount"]) for e in earnings[:2]],
                         [("REG", "40", money("25.0"), money("1000.0")), ("OT", "2", money("37.5"), money("75.0"))])
        self.assertEqual(earnings[0]["category"], {"raw": "E", "label": "Earnings", "value": "earnings"})
        self.assertEqual(earnings[2]["code"], {"raw": "FRINGE", "label": "Fringe Benefit", "value": None})
        self.assertIsNone(earnings[2]["category"])
        self.assertEqual(earnings[0]["unmapped"]["payrollVoucher[0].earning[0].department"], "OPS")
        self.assertEqual([(t["code"]["raw"], t["employee_amount"], t["employer_amount"]) for t in check["taxes"]],
                         [("00-10", money("80.0"), None), ("00-11", money("15.03"), None),
                          ("00-15", None, money("15.03"))])
        self.assertEqual(check["taxes"][2]["employer_taxable_wages"], money("1036.41"))
        self.assertEqual([(d["code"]["raw"], d["category"]["value"]) for d in check["deductions"]],
                         [("401k", "retirement_pre_tax"), ("MED", "section_125")])
        self.assertEqual([c["amount"] for c in check["employer_contributions"]], [money("189.17"), money("0.0")])
        self.assertEqual(check["payments"], [{"method": {"raw": None, "label": "checkAmt", "value": "check"},
                                              "amount": money("891.38"), "account_last4": None, "unmapped": {}}])
        self.assertEqual(check["unmapped"]["payrollVoucher[0].benefit[0].planId"], "MED")
        self.assertIsNone(check["unmapped"]["payrollVoucher[0].checkNum"])

    def test_pay_classes_other_deductions_and_direct_deposit(self):
        check = self.check("V000102")
        self.assertEqual([e["category"]["value"] for e in check["earnings"]], ["earnings", "reimbursement", "unknown"])
        self.assertEqual([(d["code"]["raw"], d["category"] and d["category"]["value"]) for d in check["deductions"]],
                         [("CLUB", "unknown"), ("UNIF", None)])
        self.assertEqual(check["deductions"][1]["code"]["label"], "Uniforms")
        self.assertEqual(len(check["payments"]), 1)
        deposit = check["payments"][0]
        self.assertEqual((deposit["method"]["value"], deposit["amount"], deposit["account_last4"]),
                         ("direct_deposit", money("242.0"), "6789"))
        self.assertEqual(deposit["unmapped"]["payrollVoucher[1].directDeposit[0].transitNum"], "[redacted]")
        self.assertEqual(check["unmapped"]["payrollVoucher[1].checkAmt"], 0.0)

    def test_both_page_keys_and_live_only_fields(self):
        arrears = self.check("V000103")
        self.assertEqual(arrears["type"]["value"], "arrears")
        self.assertEqual((arrears["earnings"], arrears["taxes"], arrears["payments"]), ([], [], []))
        found = issues_with(self.output, "spec_live_mismatch")
        self.assertEqual([i["source_path"].rsplit(".", 1)[-1] for i in found],
                         ["payrollVoucher", "hsaPeoMatch", "isManualCheck", "payAmount"])
        self.assertEqual({i["severity"] for i in found}, {"info"})

    def test_void_error_page_and_unlisted_batch(self):
        voided = self.check("V000201")
        self.assertEqual(voided["type"]["value"], "supplemental")
        self.assertEqual(voided["void_date"], "2026-01-20")
        self.assertEqual(voided["unmapped"]["payrollVoucher[0].voidVoucherId"], "V000202")
        orphan = self.check("V000901")
        self.assertIsNone(orphan["pay_run_key"])
        self.assertEqual(orphan["source"]["pay_run_id"], "202699")
        self.assertEqual(orphan["type"]["value"], "adjustment")
        missing = issues_with(self.output, "missing_section", "payrollVoucher[0].batchId")
        self.assertEqual([(i["record_key"], i["severity"]) for i in missing], [(orphan["key"], "warning")])
        page = issues_with(self.output, "missing_section", "errorCode")
        self.assertEqual([i["record_key"] for i in page], [f"{COMPANY}:run:202603"])

    def test_undocumented_codes_are_reported_once_each(self):
        found = issues_with(self.output, "undocumented_code")
        self.assertEqual([i["raw_value"] for i in found], ["HOLD", "PRNT", "Q", "ZZ", "PEND"])
        self.assertEqual({c["status"]["value"] for c in self.output["paychecks"]}, {"unknown"})

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
