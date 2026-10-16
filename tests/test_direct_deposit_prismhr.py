"""PrismHR direct deposit adapter: golden output plus the injected edge cases."""
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

    def test_line_position_is_the_deposit_id(self):
        self.assertEqual([d["source"]["deposit_id"] for d in self.lines(0)], ["0", "1"])
        self.assertTrue(all(d["priority"] is None for d in self.output["direct_deposits"]))

    def test_fixed_then_remainder(self):
        fixed, remainder = self.lines(0)
        self.assertEqual(fixed["allocation"]["method"], {"raw": "F", "label": None, "value": "fixed_amount"})
        self.assertEqual(fixed["allocation"]["amount"], {"amount": "250.0", "currency": "USD"})
        self.assertEqual(fixed["account_type"]["value"], "savings")
        self.assertEqual(remainder["allocation"], {"method": {"raw": "B", "label": None, "value": "remainder"},
                                                   "amount": None, "percent": None})

    def test_percent_methods_fill_percent_and_keep_limit_unmapped(self):
        percent = self.lines(1)[0]
        self.assertEqual(percent["allocation"]["method"]["value"], "percent")
        self.assertEqual(percent["allocation"]["percent"], "20.0")
        self.assertIsNone(percent["allocation"]["amount"])
        self.assertEqual(percent["unmapped"]["directDeposit.achVoucher[0].limit"], 500.0)
        of_net = self.lines(2)[1]
        self.assertEqual(of_net["allocation"]["method"], {"raw": "PN", "label": None, "value": "percent_of_net"})

    def test_fixed_skip_and_prenote(self):
        skip = self.lines(2)[0]
        self.assertEqual(skip["allocation"]["method"], {"raw": "FS", "label": None, "value": "fixed_amount"})
        self.assertEqual(skip["status"], {"raw": "P", "label": None, "value": "prenote"})

    def test_inconsistent_amounts_are_reported(self):
        remainder_with_amount, fixed_without = self.lines(3)
        self.assertIsNone(remainder_with_amount["allocation"]["amount"])
        self.assertEqual(remainder_with_amount["unmapped"]["directDeposit.achVoucher[0].amount"], 75.0)
        self.assertIsNone(fixed_without["allocation"]["amount"])
        found = issues_with(self.output, "inconsistent_allocation")
        self.assertEqual([i["record_key"] for i in found],
                         [remainder_with_amount["key"], fixed_without["key"]])

    def test_undocumented_method_and_instant_pay(self):
        odd = self.lines(4)[0]
        self.assertEqual(odd["allocation"]["method"]["value"], "unknown")
        self.assertEqual(odd["unmapped"]["directDeposit.achVoucher[0].amount"], 40.0)
        self.assertEqual(odd["account_type"], {"raw": "IP", "label": None, "value": "instant_pay"})
        self.assertEqual(odd["status"]["value"], "inactive")
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "undocumented_code", "method")], ["Z"])

    def test_header_fields_ride_along_in_unmapped(self):
        for deposit in self.lines(0):
            self.assertEqual(deposit["unmapped"]["directDeposit.achStatus"], "A")
            self.assertEqual(deposit["unmapped"]["directDeposit.voucherType"], "RVS")
            self.assertNotIn("directDeposit.achVoucher", deposit["unmapped"])

    def test_empty_header_and_missing_section(self):
        self.assertEqual(self.lines(5), [])
        self.assertEqual(self.lines(6), [])
        missing = issues_with(self.output, "missing_section", "directDeposit")
        self.assertEqual([i["record_key"] for i in missing], [f"prismhr:132:{self.ids[6]}"])

    def test_account_numbers_are_last_four_or_masked(self):
        unmasked = self.records[0]["directDeposit"]["achVoucher"][0]["accountNum"]
        self.assertEqual(self.lines(0)[0]["account_number_last4"], unmasked[-4:])
        self.assertIsNone(self.lines(0)[1]["account_number_last4"])
        self.assertEqual(len(issues_with(self.output, "masked_value", "accountNum")), 8)
        text = json.dumps(self.output)
        self.assertNotIn(unmasked, text)
        self.assertNotIn("accountNum\": \"*", text)

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
