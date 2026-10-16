"""PrismHR deduction adapter: golden output plus the injected edge cases."""
import unittest

from _fixtures import deductions_of, expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import prismhr


class PrismHRDeductionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("prismhr", "deduction")
        cls.output = prismhr.normalize_deductions(cls.bundle).to_dict()
        cls.ids = cls.bundle.responses["get_employee_list"]["employeeList"]["employeeId"]

    def lines(self, index):
        return deductions_of(self.output, self.ids[index])

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("prismhr", "deduction"))

    def test_is_deterministic(self):
        self.assertEqual(prismhr.normalize_deductions(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("prismhr")["employees"]}
        self.assertEqual(self.output["employees"], [])
        self.assertEqual(len(self.output["deductions"]), 11)
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIn(record["employee_key"], employee_keys)
                self.assertEqual(record["company_key"], "prismhr:132")
                self.assertTrue(record["key"].startswith(record["employee_key"] + ":ded:"))
        self.assertEqual([d["source"]["deduction_id"] for d in self.lines(0)], ["0", "1", "2"])

    def test_benefit_plan_lines_have_amount_but_no_dates(self):
        medical, life, _ = self.lines(0)
        self.assertEqual(medical["code"], {"raw": "MED", "label": "Medical", "value": None})
        self.assertEqual(medical["category"]["value"], "voluntary")
        self.assertEqual(medical["calculation"]["method"]["value"], "fixed_amount")
        self.assertIsNone(medical["effective"])
        self.assertEqual(life["calculation"]["amount"], {"amount": "0.0", "currency": "USD"})
        self.assertEqual(medical["unmapped"]["employeeDeductions.deduction[0].benefitPlanId"], "BCBSPPO1000")

    def test_percent_lines_fill_percent(self):
        retirement = self.lines(0)[2]
        self.assertEqual(retirement["category"], {"raw": "K", "label": "Pre-Tax Retirement Contribution",
                                                  "value": "retirement_pre_tax"})
        self.assertEqual(retirement["calculation"]["method"]["value"], "retirement_plan_rule")
        self.assertEqual(retirement["calculation"]["percent"], "5.0")
        self.assertIsNone(retirement["calculation"]["amount"])
        dues = self.lines(3)[1]
        self.assertEqual(dues["calculation"]["percent"], "1.5")
        self.assertEqual(dues["calculation"]["method"], {"raw": "PPR", "label": "Percentage of Pay Rate",
                                                         "value": "other"})

    def test_frequency_and_priority_are_not_mapped(self):
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIsNone(record["frequency"])
                self.assertIsNone(record["priority"])
        self.assertEqual(self.lines(0)[2]["unmapped"]["employeeDeductions.deduction[2].period"], "12345")

    def test_limit_and_each_maximum_basis(self):
        self.assertEqual(self.lines(0)[2]["limits"]["annual"], {"amount": "23000.0", "currency": "USD"})
        uniforms = self.lines(1)[0]
        self.assertEqual(uniforms["limits"]["per_pay"], {"amount": "25.0", "currency": "USD"})
        self.assertEqual(uniforms["limits"]["lifetime"], {"amount": "300.0", "currency": "USD"})
        self.assertEqual(uniforms["effective"], {"start": "2024-01-01", "end": "2026-12-31"})
        self.assertEqual(self.lines(2)[0]["limits"]["monthly"], {"amount": "900.0", "currency": "USD"})
        self.assertEqual(self.lines(3)[0]["limits"]["quarterly"], {"amount": "90.0", "currency": "USD"})

    def test_maximum_without_a_known_basis_stays_unmapped(self):
        undocumented, empty = self.lines(3)[1], self.lines(5)[0]
        for record, index in ((undocumented, 1), (empty, 0)):
            with self.subTest(key=record["key"]):
                self.assertTrue(all(v is None for v in record["limits"].values()))
                self.assertIn(f"employeeDeductions.deduction[{index}].maximum", record["unmapped"])
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "inconsistent_allocation")],
                         [empty["key"]])
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "undocumented_code", "basis")], ["W"])

    def test_employer_match_of_each_method(self):
        roth, loan = self.lines(1)[1], self.lines(2)[1]
        self.assertEqual(roth["employer_match"]["method"]["value"], "percent")
        self.assertEqual(roth["employer_match"]["percent"], "50.0")
        self.assertIsNone(roth["employer_match"]["amount"])
        self.assertEqual(loan["employer_match"]["method"]["value"], "flat")
        self.assertEqual(loan["employer_match"]["amount"], {"amount": "10.0", "currency": "USD"})
        self.assertIsNone(self.lines(1)[0]["employer_match"])

    def test_garnishment_payee_and_loan(self):
        garnishment, loan = self.lines(2)
        self.assertEqual(garnishment["category"]["value"], "garnishment")
        self.assertEqual(garnishment["calculation"]["method"]["value"], "garnishment_rule")
        self.assertEqual(garnishment["payee"], {"id": "SDU", "name": None})
        self.assertEqual(loan["category"]["value"], "loan")

    def test_undocumented_type_and_method(self):
        parking = self.lines(3)[0]
        self.assertEqual(parking["category"], {"raw": "Z", "label": None, "value": "unknown"})
        self.assertEqual(parking["calculation"]["method"], {"raw": "ZZ", "label": None, "value": "unknown"})
        self.assertEqual(sorted(i["raw_value"] for i in issues_with(self.output, "undocumented_code")),
                         ["W", "Z", "ZZ"])

    def test_bad_use_percent_and_date(self):
        charity = self.lines(5)[1]
        self.assertIsNone(charity["calculation"]["amount"])
        self.assertIsNone(charity["calculation"]["percent"])
        self.assertEqual(charity["unmapped"]["employeeDeductions.deduction[1].amount"], 5.0)
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "out_of_schema_value")], ["yes"])
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "invalid_date")], ["2025-02-30"])

    def test_empty_missing_and_error_responses(self):
        self.assertEqual(self.lines(4), [])
        self.assertEqual(self.lines(6), [])
        missing = issues_with(self.output, "missing_section", "get_deductions")
        self.assertEqual([(i["record_key"], i["severity"]) for i in missing],
                         [(f"prismhr:132:{self.ids[6]}", "info"), ("prismhr:132:X00099", "warning")])

    def test_use_percent_accepts_booleans_and_spec_letters(self):
        self.assertEqual([prismhr._use_percent(v) for v in (True, False, "T", "F", "yes", 1)],
                         [True, False, True, False, None, None])

    def test_code_tables_quote_the_spec_descriptions(self):
        for table in (prismhr.DEDUCTION_TYPE, prismhr.DEDUCTION_METHOD):
            description = resolve_code_table(table)
            for code in table.entries:
                with self.subTest(table=table.name, code=code):
                    self.assertIn(f'\\"{code}\\"', description)
        for code in prismhr.MATCH_METHOD.entries:
            self.assertIn(f"'{code}'", resolve_code_table(prismhr.MATCH_METHOD))


if __name__ == "__main__":
    unittest.main()
