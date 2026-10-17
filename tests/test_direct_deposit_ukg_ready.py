"""UKG Ready direct deposit adapter."""
import json
import unittest

from _fixtures import deposit_by_id, expected_output, fixture_bundle, issues_with, resolve_code_table
from normalization.adapters import ukg_ready

IDS = [str(12935181566 + i) for i in range(8)]


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
        self.assertEqual(len(self.output["direct_deposits"]), 9)
        for deposit in self.output["direct_deposits"]:
            with self.subTest(key=deposit["key"]):
                self.assertIn(deposit["employee_key"], employee_keys)
        self.assertEqual(self.output["company"]["key"], "ukg-ready:33704016")
        self.assertIsNone(self.output["company"]["ein"])

    def test_flat_amount_and_percent_of_net(self):
        flat = deposit_by_id(self.output, "47481000")
        self.assertEqual(flat["allocation"]["method"],
                         {"raw": "FLAT_AMOUNT", "label": "Flat $ Amount", "value": "fixed_amount"})
        self.assertIsNotNone(flat["allocation"]["amount"])
        self.assertIsNone(flat["allocation"]["percent"])
        self.assertEqual(flat["account_type"]["value"], "checking")
        net = deposit_by_id(self.output, "47482000")
        self.assertEqual(net["allocation"]["method"]["value"], "percent_of_net")
        self.assertEqual(net["allocation"]["percent"], "10.0")
        self.assertIsNone(net["allocation"]["amount"])

    def test_prenote_and_frequency_stay_unmapped(self):
        unmapped = deposit_by_id(self.output, "47481000")["unmapped"]
        self.assertEqual(unmapped["deposits[0].pre_note_status"], "READY_TO_SEND")
        self.assertEqual(unmapped["deposits[0].payroll_frequency.type"], "EVERY_PAY")
        self.assertEqual(unmapped["_routing_type"], "ABA")

    def test_one_start_date_is_invalid(self):
        found = issues_with(self.output, "invalid_date")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found],
                         [(f"ukg-ready:33704016:{IDS[7]}:dd:47481007", "2025-02-30")])

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
