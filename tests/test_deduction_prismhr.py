"""PrismHR deduction adapter."""
import copy
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
        self.assertEqual(len(self.output["deductions"]), 13)
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIn(record["employee_key"], employee_keys)
                self.assertEqual(record["company_key"], "prismhr:132")
                self.assertTrue(record["key"].startswith(record["employee_key"] + ":ded:"))

    def test_ordinary_medical_is_a_fixed_amount(self):
        medical = self.lines(0)[0]
        self.assertEqual(medical["code"], {"raw": "MED", "label": "Medical", "value": None})
        self.assertEqual(medical["category"]["value"], "voluntary")
        self.assertEqual(medical["calculation"]["method"]["value"], "fixed_amount")
        self.assertEqual(medical["effective"]["start"], "2024-01-01")

    def test_one_start_date_is_invalid(self):
        bad = self.lines(7)[0]
        self.assertIsNone(bad["effective"])
        found = issues_with(self.output, "invalid_date", "startDate")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(bad["key"], "2025-02-30")])

    def test_payee_name_comes_from_the_payee_setup(self):
        lines = self.lines(7)
        self.assertEqual(lines[1]["payee"], {"id": "MEDCO", "name": "Medco Retirement Plan Services"})
        self.assertEqual(lines[4]["payee"], {"id": "SDU-PA", "name": "Pennsylvania SCDU"})
        self.assertIsNone(lines[0]["payee"])
        self.assertEqual(issues_with(self.output, "missing_lookup", "cutbackPayeeCode"), [])

    def test_payee_missing_from_payee_setup_keeps_the_id(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses["get_payee"].pop("SDU-PA")
        bundle.responses["get_payee"]["MEDCO"] = {
            "errorCode": "1", "errorMessage": "this user session is not authorized for the method specified",
            "extension": None}
        output = prismhr.normalize_deductions(bundle).to_dict()
        lines = deductions_of(output, self.ids[7])
        self.assertEqual([lines[1]["payee"], lines[4]["payee"]],
                         [{"id": "MEDCO", "name": None}, {"id": "SDU-PA", "name": None}])
        found = issues_with(output, "missing_lookup", "cutbackPayeeCode")
        self.assertEqual([(i["record_key"], i["raw_value"], i["severity"]) for i in found],
                         [(lines[1]["key"], "MEDCO", "warning"), (lines[4]["key"], "SDU-PA", "warning")])
        self.assertIn("not authorized", found[0]["message"])

    def test_payee_setup_is_optional(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses.pop("get_payee")
        output = prismhr.normalize_deductions(bundle).to_dict()
        lines = deductions_of(output, self.ids[7])
        self.assertEqual(lines[1]["payee"], {"id": "MEDCO", "name": None})
        found = issues_with(output, "missing_section", "get_payee")
        self.assertEqual([(i["source_path"], i["severity"], i["record_key"]) for i in found],
                         [("responses.get_payee", "info", None)])
        self.assertFalse(issues_with(output, "missing_lookup", "cutbackPayeeCode"))

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
