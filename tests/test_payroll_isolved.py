"""isolved payroll adapter: golden output plus the injected edge cases."""
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import isolved

COMPANY = "isolved:4046-5806"


def money(amount):
    return {"amount": amount, "currency": "USD"}


def check_key(employee_id, check_id):
    return f"{COMPANY}:{employee_id}:chk:{check_id}"


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
        self.assertEqual(len(self.output["pay_runs"]), 5)
        joined = {c["source"]["paycheck_id"]: c["pay_run_key"] for c in self.output["paychecks"]}
        self.assertEqual(joined, {"21000101": f"{COMPANY}:run:4100001", "21000102": f"{COMPANY}:run:4100002",
                                  "21000201": None, "21000301": None, "21000601": f"{COMPANY}:run:4100003"})
        for check in self.output["paychecks"]:
            with self.subTest(key=check["key"]):
                self.assertIn(check["employee_key"], employee_keys)
                self.assertEqual(check["company_key"], COMPANY)
        self.assertEqual(self.check("21000101")["source"]["pay_run_id"], "4100001")
        self.assertIsNone(self.check("21000301")["source"]["pay_run_id"])

    def test_run_fields(self):
        run = self.pay_run("4100001")
        self.assertEqual(run["type"], {"raw": "Regular Payroll", "label": None, "value": "regular"})
        self.assertEqual(run["status"], {"raw": "Completed Payroll Run", "label": None, "value": "completed"})
        self.assertEqual((run["pay_date"], run["period"]), ("2026-01-09", {"start": "2025-12-22", "end": "2026-01-04"}))
        self.assertEqual(run["description"], "1st Payroll of Month")
        self.assertEqual(run["pay_group"], {"raw": "7627", "label": None, "value": None})
        self.assertEqual(run["unmapped"]["payroll_run_history['7627'][0].runNumber"], 1)
        scheduled = self.pay_run("4100002")
        self.assertEqual(scheduled["status"]["value"], "open")
        self.assertIsNone(scheduled["description"])
        self.assertIsNone(scheduled["period"])

    def test_labels_off_the_allowlists(self):
        found = issues_with(self.output, "unmapped_label")
        self.assertEqual([i["raw_value"] for i in found], ["Data Conversion", "Payroll Voided", "Manual Check"])
        self.assertEqual(self.pay_run("4100003")["type"]["value"], "unknown")
        self.assertEqual(self.check("21000201")["type"], {"raw": "Manual Check", "label": None, "value": "unknown"})

    def test_checks_that_join_no_run(self):
        found = issues_with(self.output, "missing_section", "payrollRunNumber")
        self.assertEqual([(i["record_key"], i["severity"]) for i in found],
                         [(check_key(859202, 21000201), "warning"), (check_key(859203, 21000301), "warning")])
        self.assertIn("more than one", found[0]["message"])
        self.assertIn("no captured run", found[1]["message"])

    def test_check_with_detail(self):
        check = self.check("21000101")
        self.assertEqual(check["type"], {"raw": "Adjustment", "label": None, "value": "adjustment"})
        self.assertEqual((check["check_number"], check["gross_pay"], check["net_pay"]),
                         ("5001", money("1500.0"), money("1164.67")))
        self.assertEqual([(e["code"]["raw"], e["code"]["label"], e["hours"], e["amount"]) for e in check["earnings"]],
                         [("01", "Regular", "80.0", money("1450.0")), ("14", "Commission", "0.0", money("50.0")),
                          ("001", "401k Match", "0.0", money("45.0"))])
        self.assertEqual([e["category"] for e in check["earnings"]],
                         [None, None, {"raw": None, "label": "isMemoEarning", "value": "memo"}])
        self.assertEqual(check["earnings"][0]["unmapped"]["results[0].earnings[0].ytdDollars"], 1450.0)
        self.assertEqual([(t["code"], t["employee_amount"], t["employer_amount"]) for t in check["taxes"]],
                         [({"raw": None, "label": "FEDERAL WH", "value": None}, money("120.0"), None),
                          ({"raw": None, "label": "SOC SEC ER", "value": None}, None, money("93.0"))])
        self.assertEqual(check["taxes"][0]["employee_taxable_wages"], money("1334.67"))
        self.assertEqual([(d["code"]["raw"], d["amount"]) for d in check["deductions"]],
                         [("030", money("90.33")), ("32", money("75.0")), ("GARN", money("50.0"))])
        contributions = check["employer_contributions"]
        self.assertEqual([(c["code"]["label"], c["amount"]) for c in contributions], [("401(k)", money("45.0"))])
        self.assertEqual(contributions[0]["unmapped"]["results[0].benefits[0].checkEmployeeDeduction"], 75.0)
        self.assertEqual(check["unmapped"]["results[0].benefits[1].benefitTitle"], "Leave Accrual")
        self.assertEqual([(p["method"]["label"], p["amount"], p["account_last4"]) for p in check["payments"]],
                         [("directDeposits", money("1164.67"), "4321")])
        self.assertEqual(check["unmapped"]["results[0].directDepositAmount"], 1164.67)
        self.assertEqual(check["unmapped"]["results[0].employeeSSN"], "[redacted]")
        self.assertIn("results[0].employeeName", check["unmapped"])

    def test_checks_without_detail(self):
        reissued = self.check("21000102")
        self.assertEqual((reissued["taxes"], reissued["employer_contributions"]), ([], []))
        self.assertEqual(reissued["payments"], [{"method": {"raw": None, "label": "checkAmount", "value": "check"},
                                                 "amount": money("1080.0"), "account_last4": None, "unmapped": {}}])
        self.assertEqual(reissued["unmapped"]["results[1].reissueCheckNumber"], 5010)
        self.assertIsNone(reissued["void_date"])
        unjoined = self.check("21000301")
        self.assertEqual([(p["method"]["label"], p["method"]["value"], p["amount"]) for p in unjoined["payments"]],
                         [("directDepositAmount", "direct_deposit", money("190.0"))])
        found = issues_with(self.output, "missing_section", "check_detail")
        self.assertEqual([(i["record_key"], i["severity"]) for i in found],
                         [(check_key(859201, 21000102), "info"), (check_key(859203, 21000301), "info")])

    def test_tax_side_that_is_not_a_boolean(self):
        tax = self.check("21000201")["taxes"][0]
        self.assertEqual(tax["code"]["label"], "FEDERAL WH")
        self.assertIsNone(tax["employee_amount"])
        self.assertIsNone(tax["employer_amount"])
        self.assertEqual(tax["unmapped"]["results[0].taxes[0].checkDollars"], 39.68)
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "out_of_schema_value")], ["yes"])

    def test_employees_without_checks(self):
        ids = {c["source"]["employee_id"] for c in self.output["paychecks"]}
        self.assertEqual(ids, {"859201", "859202", "859203", "859206"})
        found = issues_with(self.output, "missing_section", "checks")
        self.assertEqual([(i["record_key"], i["severity"]) for i in found], [(f"{COMPANY}:859205", "info")])

    def test_allowlists_cite_the_spec_fields(self):
        for table in (isolved.RUN_TYPE, isolved.RUN_STATUS, isolved.CHECK_TYPE):
            with self.subTest(table=table.name):
                self.assertEqual(table.kind, "label")
                self.assertIn(resolve_code_table(table)["description"], table.evidence)


if __name__ == "__main__":
    unittest.main()
