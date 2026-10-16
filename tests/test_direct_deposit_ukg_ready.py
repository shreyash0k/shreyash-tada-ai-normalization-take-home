"""UKG Ready direct deposit adapter: golden output plus the injected edge cases."""
import json
import unittest

from _fixtures import deposit_by_id, deposits_of, expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import ukg_ready

IDS = [str(12935181566 + i) for i in range(6)]


class UkgReadyDirectDepositChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("ukg-ready", "direct-deposit")
        cls.output = ukg_ready.normalize_direct_deposits(cls.bundle).to_dict()

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("ukg-ready", "direct-deposit"))

    def test_is_deterministic(self):
        self.assertEqual(ukg_ready.normalize_direct_deposits(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("ukg-ready")["employees"]}
        self.assertEqual(len(self.output["direct_deposits"]), 10)
        for deposit in self.output["direct_deposits"]:
            with self.subTest(key=deposit["key"]):
                self.assertIn(deposit["employee_key"], employee_keys)
        self.assertEqual(self.output["company"]["key"], "ukg-ready:33704016")
        self.assertIsNone(self.output["company"]["ein"])

    def test_every_calc_method_maps(self):
        methods = {d["allocation"]["method"]["raw"]: d["allocation"]["method"]["value"]
                   for d in self.output["direct_deposits"]}
        self.assertEqual(methods, {
            "FULL": "remainder", "FLAT_AMOUNT": "fixed_amount", "NET_PAY": "percent_of_net",
            "GROSS_EARNING": "percent_of_gross", "DIRECT_DEPOSIT_PER_OF_REMAINDER": "percent_of_remainder",
        })
        self.assertEqual(deposit_by_id(self.output, "47480102")["allocation"]["method"]["label"], "Flat $ Amount")

    def test_amount_and_percentage_follow_the_calc_method(self):
        flat = deposit_by_id(self.output, "47480102")
        self.assertEqual(flat["allocation"]["amount"], {"amount": "1000.0", "currency": "USD"})
        self.assertIsNone(flat["allocation"]["percent"])
        net = deposit_by_id(self.output, "47480103")
        self.assertEqual(net["allocation"]["percent"], "15.0")
        self.assertIsNone(net["allocation"]["amount"])
        self.assertEqual(net["account_type"]["value"], "savings")

    def test_sequence_status_and_effective_dates(self):
        lines = deposits_of(self.output, IDS[1])
        self.assertEqual([d["priority"] for d in lines], [1, 2, 3])
        inactive = deposit_by_id(self.output, "47480105")
        self.assertEqual(inactive["status"], {"raw": "false", "label": None, "value": "inactive"})
        self.assertEqual(inactive["effective"], {"start": "1900-12-31", "end": "2017-07-13"})
        self.assertEqual(deposit_by_id(self.output, "47480101")["status"]["value"], "active")

    def test_prenote_and_frequency_stay_unmapped(self):
        unmapped = deposit_by_id(self.output, "47480102")["unmapped"]
        self.assertEqual(unmapped["deposits[0].pre_note_status"], "CANCELED")
        self.assertEqual(unmapped["deposits[0].payroll_frequency.type"], "EVERY_PAY")
        self.assertEqual(unmapped["_routing_type"], "ABA")

    def test_short_account_number_is_not_emitted(self):
        self.assertIsNone(deposit_by_id(self.output, "47480105")["account_number_last4"])
        found = issues_with(self.output, "invalid_number", "account_number")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found],
                         [(f"ukg-ready:33704016:{IDS[2]}:dd:47480105", "[redacted]")])

    def test_out_of_schema_account_type_and_invalid_date(self):
        odd = deposit_by_id(self.output, "47480107")
        self.assertEqual(odd["account_type"], {"raw": "MONEY_MARKET", "label": None, "value": "unknown"})
        self.assertEqual(odd["effective"], {"start": None, "end": "2099-12-31"})
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "out_of_schema_value")], ["MONEY_MARKET"])
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "invalid_date")], ["2025-02-30"])

    def test_reserve_live_check_has_no_bank_fields(self):
        reserve = deposit_by_id(self.output, "47480108")
        self.assertIsNone(reserve["routing_number"])
        self.assertIsNone(reserve["account_number_last4"])
        self.assertIsNone(reserve["account_type"])
        self.assertEqual(reserve["unmapped"]["deposits[1].type"], "RESERVE_LIVE_CHECK")

    def test_flat_amount_without_amount(self):
        missing = deposit_by_id(self.output, "47480109")
        self.assertIsNone(missing["allocation"]["amount"])
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "inconsistent_allocation")],
                         [missing["key"]])

    def test_missing_response(self):
        self.assertEqual(deposits_of(self.output, IDS[4]), [])
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "missing_section", "direct_deposits")],
                         [f"ukg-ready:33704016:{IDS[4]}"])

    def test_code_tables_cover_the_schema_enums_exactly(self):
        for table in (ukg_ready.DEPOSIT_CALC_METHOD, ukg_ready.DEPOSIT_ACCOUNT_TYPE):
            with self.subTest(table=table.name):
                self.assertEqual(sorted(table.entries), sorted(resolve_code_table(table)))

    def test_secrets_are_not_emitted(self):
        text = json.dumps(self.output)
        self.assertIn("notes?token=[redacted]", text)
        self.assertNotIn("token=synthetic", text)
        for envelope in self.bundle.responses["direct_deposits"].values():
            for line in envelope["deposits"]:
                if "account_number" in line and len(line["account_number"]) >= 6:
                    self.assertNotIn(line["account_number"], text)


if __name__ == "__main__":
    unittest.main()
