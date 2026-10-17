"""UKG Ready deduction adapter."""
import unittest

from _fixtures import deduction_by_key, deductions_of, expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import ukg_ready

IDS = [str(12935181566 + i) for i in range(8)]


def key(index, deduction_id):
    return f"ukg-ready:33704016:{IDS[index]}:ded:{deduction_id}"


class UkgReadyDeductionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("ukg-ready", "deduction")
        cls.output = ukg_ready.normalize_deductions(cls.bundle).to_dict()

    def record(self, index, deduction_id):
        return deduction_by_key(self.output, key(index, deduction_id))

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("ukg-ready", "deduction"))

    def test_is_deterministic(self):
        self.assertEqual(ukg_ready.normalize_deductions(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("ukg-ready")["employees"]}
        self.assertEqual(len(self.output["deductions"]), 9)
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIn(record["employee_key"], employee_keys)
                self.assertEqual(record["company_key"], "ukg-ready:33704016")
        self.assertEqual([d["priority"] for d in deductions_of(self.output, IDS[0])], [1, 2])

    def test_amount_percent_and_limits_join_from_detail(self):
        medical = self.record(0, 198000)
        self.assertEqual(medical["code"], {"raw": "Medical", "label": "Medical", "value": None})
        self.assertIsNotNone(medical["calculation"]["amount"])
        self.assertEqual(medical["limits"]["annual"]["amount"], "23000")
        self.assertEqual(medical["limits"]["per_pay"]["amount"], "500")
        self.assertEqual(medical["employer_match"]["annual_max"]["amount"], "5000")
        self.assertEqual(medical["payee"], {"id": "65792", "name": "Retirement Vendor"})
        percent = self.record(0, 198100)
        self.assertEqual(percent["calculation"]["percent"], "6")
        self.assertIsNone(percent["calculation"]["amount"])

    def test_method_type_is_reported_once(self):
        found = issues_with(self.output, "undocumented_code", "ee_calc_method.method.type")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found],
                         [(key(0, 198000), "FLAT_AMOUNT")])

    def test_frequency_table_covers_the_schema_enum_exactly(self):
        table = ukg_ready.DEDUCTION_FREQUENCY
        self.assertEqual(sorted(table.entries), sorted(resolve_code_table(table)))


if __name__ == "__main__":
    unittest.main()
