"""isolved deduction adapter (payItems)."""
import unittest

from _fixtures import deductions_of, expected_output, fixture_bundle, issues_with
from normalization.adapters import isolved

COMPANY_KEY = "isolved:4046-5806"


class IsolvedDeductionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("isolved", "deduction")
        cls.output = isolved.normalize_deductions(cls.bundle).to_dict()
        cls.ids = [str(r["id"]) for page in cls.bundle.responses["employees"] for r in page["results"]]

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("isolved", "deduction"))

    def test_is_deterministic(self):
        self.assertEqual(isolved.normalize_deductions(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("isolved")["employees"]}
        self.assertEqual(len(self.output["deductions"]), 9)
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIn(record["employee_key"], employee_keys)
                self.assertEqual(record["company_key"], COMPANY_KEY)
                self.assertEqual(record["source"]["deduction_id"], record["key"].rsplit(":", 1)[1])

    def test_medical_amount_and_retirement_percent(self):
        medical = deductions_of(self.output, self.ids[0])[0]
        self.assertEqual(medical["code"]["label"], "Medical Pre-tax")
        self.assertIsNotNone(medical["calculation"]["amount"])
        self.assertIsNone(medical["calculation"]["percent"])
        percent = deductions_of(self.output, self.ids[7])[1]
        self.assertEqual(percent["code"]["label"], "401K")
        self.assertEqual(percent["calculation"]["percent"], "6.0")
        self.assertEqual(percent["effective"]["end"], "2026-12-31")

    def test_one_stop_date_is_invalid(self):
        bad = deductions_of(self.output, self.ids[7])[0]
        self.assertIsNone(bad["effective"]["end"])
        found = issues_with(self.output, "invalid_date", "stopDate")
        self.assertEqual([i["record_key"] for i in found], [bad["key"]])


if __name__ == "__main__":
    unittest.main()
