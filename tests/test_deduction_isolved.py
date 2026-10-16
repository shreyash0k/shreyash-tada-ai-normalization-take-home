"""isolved deduction adapter (payItems): golden output plus the injected edge cases."""
import unittest

from _fixtures import deduction_by_key, deductions_of, expected_output, fixture_bundle, issues_with
from normalization.adapters import isolved

COMPANY_KEY = "isolved:4046-5806"


class IsolvedDeductionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("isolved", "deduction")
        cls.output = isolved.normalize_deductions(cls.bundle).to_dict()
        cls.ids = [str(r["id"]) for page in cls.bundle.responses["employees"] for r in page["results"]]

    def record(self, index, item_id):
        return deduction_by_key(self.output, f"{COMPANY_KEY}:{self.ids[index]}:ded:{item_id}")

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("isolved", "deduction"))

    def test_is_deterministic(self):
        self.assertEqual(isolved.normalize_deductions(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("isolved")["employees"]}
        self.assertEqual(len(self.output["deductions"]), 6)
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIn(record["employee_key"], employee_keys)
                self.assertEqual(record["company_key"], COMPANY_KEY)
                self.assertEqual(record["source"]["deduction_id"], record["key"].rsplit(":", 1)[1])

    def test_only_deduction_items_are_kept(self):
        names = [d["code"]["label"] for d in deductions_of(self.output, self.ids[0])]
        self.assertEqual(names, ["Medical Pre-tax", "401K"])
        self.assertNotIn("Bonus", str(self.output["deductions"]))
        unknown = issues_with(self.output, "unmapped_label", "payItemType")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in unknown],
                         [(f"{COMPANY_KEY}:{self.ids[2]}", "Benefit")])

    def test_amount_and_percent_params(self):
        medical, retirement = deductions_of(self.output, self.ids[0])
        self.assertEqual(medical["code"]["raw"], "030")
        self.assertIsNotNone(medical["calculation"]["amount"])
        self.assertIsNone(medical["calculation"]["percent"])
        self.assertEqual(retirement["calculation"]["amount"], {"amount": "0.0", "currency": "USD"})
        self.assertEqual(retirement["calculation"]["percent"], "6.0")
        self.assertEqual(medical["effective"], {"start": "2024-01-01", "end": None})

    def test_no_category_method_or_frequency(self):
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIsNone(record["category"])
                self.assertIsNone(record["calculation"]["method"])
                self.assertIsNone(record["frequency"])

    def test_other_params_are_reported_once_per_label(self):
        found = issues_with(self.output, "unmapped_label", "calcParams")
        self.assertEqual([i["raw_value"] for i in found], ["Amount2", "Rate"])
        united_way = self.record(1, 770203)
        self.assertEqual(united_way["unmapped"]["pay_items[2].calcParams[1].paramType"], "Amount2")
        self.assertEqual(united_way["effective"], {"start": "2025-01-01", "end": "2025-12-31"})

    def test_balance_is_a_live_only_field(self):
        self.assertEqual(self.record(1, 770203)["unmapped"]["pay_items[2].balance"], 0.0)
        self.assertEqual(len(issues_with(self.output, "spec_live_mismatch")), 1)

    def test_item_without_code_keeps_its_name(self):
        self.assertEqual(self.record(1, 770204)["code"], {"raw": None, "label": "FSA Medical pos", "value": None})

    def test_no_params_and_invalid_date(self):
        loan = self.record(2, 770303)
        self.assertEqual(loan["calculation"], {"method": None, "amount": None, "percent": None})
        self.assertEqual(loan["effective"], {"start": "2022-06-01", "end": None})
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "invalid_date")], ["2025-02-30T00:00:00"])

    def test_empty_and_missing_pay_items(self):
        self.assertEqual(deductions_of(self.output, self.ids[3]), [])
        self.assertEqual(deductions_of(self.output, self.ids[4]), [])
        missing = issues_with(self.output, "missing_section", "pay_items")
        self.assertEqual([i["record_key"] for i in missing], [f"{COMPANY_KEY}:{self.ids[4]}"])


if __name__ == "__main__":
    unittest.main()
