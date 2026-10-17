"""PrismHR direct deposit adapter."""
import json
import unittest

from _fixtures import deposits_of, expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import prismhr


class PrismHRDirectDepositChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("prismhr", "direct-deposit")
        cls.output = prismhr.normalize_direct_deposits(cls.bundle).to_dict()
        cls.records = [r for response in cls.bundle.responses["get_employee_direct_deposit"]
                       for r in response["employee"]]
        cls.ids = [r["id"] for r in cls.records]

    def lines(self, index):
        return deposits_of(self.output, self.ids[index])

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("prismhr", "direct-deposit"))

    def test_is_deterministic(self):
        self.assertEqual(prismhr.normalize_direct_deposits(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("prismhr")["employees"]}
        self.assertEqual(self.output["employees"], [])
        self.assertEqual(len(self.output["direct_deposits"]), 9)
        for deposit in self.output["direct_deposits"]:
            with self.subTest(key=deposit["key"]):
                self.assertIn(deposit["employee_key"], employee_keys)
                self.assertEqual(deposit["company_key"], "prismhr:132")
                self.assertTrue(deposit["key"].startswith(deposit["employee_key"] + ":dd:"))

    def test_fixed_and_percent_lines(self):
        fixed, percent = self.lines(0)
        self.assertEqual(fixed["allocation"]["method"], {"raw": "F", "label": None, "value": "fixed_amount"})
        self.assertIsNotNone(fixed["allocation"]["amount"])
        self.assertEqual(fixed["account_type"]["value"], "checking")
        self.assertEqual(percent["allocation"]["method"]["value"], "percent")
        self.assertEqual(percent["allocation"]["percent"], "10.0")
        self.assertIsNone(percent["allocation"]["amount"])
        self.assertTrue(all(d["priority"] is None for d in self.output["direct_deposits"]))

    def test_header_fields_ride_along_in_unmapped(self):
        for deposit in self.lines(0):
            self.assertEqual(deposit["unmapped"]["directDeposit.achStatus"], "A")
            self.assertEqual(deposit["unmapped"]["directDeposit.voucherType"], "RVS")
            self.assertNotIn("directDeposit.achVoucher", deposit["unmapped"])

    def test_one_account_number_is_masked(self):
        unmasked = self.records[0]["directDeposit"]["achVoucher"][0]["accountNum"]
        self.assertEqual(self.lines(0)[0]["account_number_last4"], unmasked[-4:])
        masked = self.lines(7)[0]
        self.assertIsNone(masked["account_number_last4"])
        found = issues_with(self.output, "masked_value", "accountNum")
        self.assertEqual([i["record_key"] for i in found], [masked["key"]])
        text = json.dumps(self.output)
        self.assertNotIn(unmasked, text)

    def test_code_tables_quote_the_spec_descriptions(self):
        for table in (prismhr.ACCOUNT_TYPE, prismhr.DEPOSIT_METHOD, prismhr.DEPOSIT_STATUS):
            description = resolve_code_table(table)
            for code in table.entries:
                with self.subTest(table=table.name, code=code):
                    self.assertIn(f"'{code}'" if code != "IP" else "IP (instant pay)", description)

    def test_routing_and_bank_are_kept(self):
        line = self.records[0]["directDeposit"]["achVoucher"][0]
        deposit = self.lines(0)[0]
        self.assertEqual(deposit["routing_number"], line["transitNum"])
        self.assertEqual(deposit["bank_name"], line["bankName"])


if __name__ == "__main__":
    unittest.main()
