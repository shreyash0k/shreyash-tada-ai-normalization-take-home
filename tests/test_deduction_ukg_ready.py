"""UKG Ready deduction adapter: golden output plus the injected edge cases."""
import unittest

from _fixtures import deduction_by_key, deductions_of, expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import ukg_ready

IDS = [str(12935181566 + i) for i in range(6)]


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
        self.assertEqual(len(self.output["deductions"]), 7)
        for record in self.output["deductions"]:
            with self.subTest(key=record["key"]):
                self.assertIn(record["employee_key"], employee_keys)
                self.assertEqual(record["company_key"], "ukg-ready:33704016")
        self.assertEqual([d["priority"] for d in deductions_of(self.output, IDS[0])], [1, 2])

    def test_list_and_detail_are_joined(self):
        retirement = self.record(0, 197121)
        self.assertEqual(retirement["code"], {"raw": "401k", "label": "401k", "value": None})
        self.assertEqual(retirement["calculation"]["percent"], "6")
        self.assertIsNone(retirement["calculation"]["amount"])
        self.assertEqual(retirement["frequency"], {"raw": "EVERY_SCHEDULED_PAY", "label": "Every Scheduled Pay",
                                                   "value": "every_pay"})
        self.assertEqual(retirement["limits"]["per_pay"], {"amount": "500", "currency": "USD"})
        self.assertEqual(retirement["limits"]["annual"], {"amount": "23000", "currency": "USD"})
        self.assertEqual(retirement["employer_match"]["annual_max"], {"amount": "5000", "currency": "USD"})
        self.assertEqual(retirement["payee"], {"id": "65792", "name": "Retirement Vendor"})
        self.assertEqual(retirement["unmapped"]["deductions[0].memo"], "Synthetic memo 197121")

    def test_open_ended_end_date_is_kept(self):
        self.assertEqual(self.record(0, 197121)["effective"], {"start": "2017-04-12", "end": "9999-12-31"})
        self.assertEqual(self.record(1, 197132)["effective"]["end"], "2026-06-30")

    def test_method_type_has_no_enum_and_is_reported_once(self):
        flat = self.record(0, 197122)
        self.assertEqual(flat["calculation"]["method"], {"raw": "FLAT_AMOUNT", "label": "Flat $ Amount",
                                                         "value": "unknown"})
        self.assertEqual(flat["calculation"]["amount"], {"amount": "150", "currency": "USD"})
        found = issues_with(self.output, "undocumented_code", "ee_calc_method")
        self.assertEqual([i["raw_value"] for i in found], ["EARNING_LIST", "FLAT_AMOUNT"])

    def test_frequencies_without_a_counterpart_map_to_other(self):
        self.assertEqual(self.record(1, 197131)["frequency"]["value"], "benefit_plan")
        self.assertEqual(self.record(1, 197132)["frequency"]["value"], "other")
        self.assertEqual(self.record(5, 197161)["frequency"]["value"], "other")

    def test_both_amount_and_percent_and_out_of_schema_frequency(self):
        gym = self.record(2, 197141)
        self.assertEqual(gym["calculation"]["amount"], {"amount": "15", "currency": "USD"})
        self.assertIsNone(gym["calculation"]["percent"])
        self.assertEqual(gym["unmapped"]["deductions[0].ee_calc_method.percent"], 2)
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "inconsistent_allocation")], [gym["key"]])
        self.assertEqual(gym["frequency"], {"raw": "WEEKLY", "label": "Weekly", "value": "unknown"})
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "out_of_schema_value")], ["WEEKLY"])

    def test_line_without_detail_keeps_list_fields(self):
        parking = self.record(2, 197142)
        self.assertEqual(parking["code"]["raw"], "Parking")
        self.assertEqual(parking["priority"], 2)
        self.assertEqual(parking["calculation"], {"method": None, "amount": None, "percent": None})
        self.assertIsNone(parking["frequency"])
        missing = issues_with(self.output, "missing_section", "deduction_detail")
        self.assertEqual([(i["record_key"], i["severity"]) for i in missing], [(parking["key"], "warning")])

    def test_vendor_without_name_and_invalid_date(self):
        club = self.record(5, 197161)
        self.assertEqual(club["payee"], {"id": "65794", "name": None})
        self.assertEqual(club["effective"], {"start": None, "end": "9999-12-31"})
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "invalid_date")], ["2025-13-01"])

    def test_empty_and_missing_lists(self):
        self.assertEqual(deductions_of(self.output, IDS[3]), [])
        self.assertEqual(deductions_of(self.output, IDS[4]), [])
        missing = issues_with(self.output, "missing_section", "deductions")
        self.assertEqual([(i["record_key"], i["severity"]) for i in missing], [(f"ukg-ready:33704016:{IDS[4]}", "info")])

    def test_frequency_table_covers_the_schema_enum_exactly(self):
        table = ukg_ready.DEDUCTION_FREQUENCY
        self.assertEqual(sorted(table.entries), sorted(resolve_code_table(table)))


if __name__ == "__main__":
    unittest.main()
