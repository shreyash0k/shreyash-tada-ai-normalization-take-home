"""isolved direct deposit adapter: golden output plus the injected edge cases."""
import copy
import json
import unittest

from _fixtures import (
    deposit_by_id,
    deposits_of,
    expected_output,
    fixture_bundle,
    issues_with,
    raw_bundle,
    resolve_code_table,
)
from normalization.adapters import isolved
from normalization.bundle import parse_bundle

IDS = [str(859201 + i) for i in range(6)]


class IsolvedDirectDepositChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("isolved", "direct-deposit")
        cls.output = isolved.normalize_direct_deposits(cls.bundle).to_dict()

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("isolved", "direct-deposit"))

    def test_is_deterministic(self):
        self.assertEqual(isolved.normalize_direct_deposits(self.bundle).to_dict(), self.output)

    def test_lines_link_to_employees_and_company(self):
        employee_keys = {e["key"] for e in expected_output("isolved")["employees"]}
        self.assertEqual(len(self.output["direct_deposits"]), 8)
        for deposit in self.output["direct_deposits"]:
            with self.subTest(key=deposit["key"]):
                self.assertIn(deposit["employee_key"], employee_keys)
                self.assertEqual(deposit["key"], f"{deposit['employee_key']}:dd:{deposit['source']['deposit_id']}")
        self.assertEqual(self.output["company"]["key"], "isolved:4046-5806")
        self.assertEqual(self.output["company"]["source"]["secondary_ids"], {"legalCode": "BK422-1"})

    def test_sequence_zero_is_the_net_pay_remainder(self):
        net = deposit_by_id(self.output, "640101")
        self.assertEqual(net["allocation"], {
            "method": {"raw": None, "label": "Net Pay (sequence 0)", "value": "remainder"},
            "amount": None, "percent": None})
        self.assertEqual(net["priority"], 0)

    def test_method_follows_the_field_that_is_set(self):
        fixed = deposit_by_id(self.output, "640102")
        self.assertEqual(fixed["allocation"]["method"]["value"], "fixed_amount")
        self.assertEqual(fixed["allocation"]["amount"], {"amount": "200.0", "currency": "USD"})
        self.assertEqual(fixed["priority"], 1)
        percent = deposit_by_id(self.output, "640106")
        self.assertEqual(percent["allocation"]["method"]["value"], "percent")
        self.assertEqual(percent["allocation"]["percent"], "25.0")

    def test_inconsistent_allocations_are_reported(self):
        neither = deposit_by_id(self.output, "640104")
        both = deposit_by_id(self.output, "640107")
        net_with_amount = deposit_by_id(self.output, "640108")
        self.assertEqual(neither["allocation"]["method"]["value"], "unknown")
        self.assertEqual(both["allocation"]["method"]["value"], "unknown")
        self.assertEqual(both["unmapped"]["direct_deposits[1].amount"], 50.0)
        self.assertEqual(both["unmapped"]["direct_deposits[1].percent"], 10.0)
        self.assertEqual(net_with_amount["allocation"]["method"]["value"], "remainder")
        self.assertEqual(net_with_amount["unmapped"]["direct_deposits[2].amount"], 10.0)
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "inconsistent_allocation")],
                         [neither["key"], both["key"], net_with_amount["key"]])

    def test_inactive_line_without_sequence(self):
        inactive = deposit_by_id(self.output, "640105")
        self.assertIsNone(inactive["priority"])
        self.assertEqual(inactive["status"], {"raw": "Inactive", "label": None, "value": "inactive"})
        self.assertEqual(inactive["allocation"]["method"]["value"], "fixed_amount")

    def test_labels_outside_the_allowlist_stay_raw(self):
        self.assertEqual(deposit_by_id(self.output, "640106")["account_type"],
                         {"raw": "Savings", "label": None, "value": "unknown"})
        self.assertEqual(deposit_by_id(self.output, "640107")["status"]["value"], "unknown")
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "unmapped_label")], ["Savings", "Pending"])
        self.assertEqual(deposit_by_id(self.output, "640101")["account_type"]["value"], "checking")

    def test_label_tables_point_at_free_text_fields(self):
        for table in (isolved.DEPOSIT_ACCOUNT_TYPE, isolved.DEPOSIT_STATUS):
            with self.subTest(table=table.name):
                field = resolve_code_table(table)
                self.assertEqual(field["type"], "string")
                self.assertNotIn("enum", field)
                self.assertEqual(table.kind, "label")

    def test_frequency_stays_unmapped(self):
        self.assertEqual(deposit_by_id(self.output, "640101")["unmapped"]["direct_deposits[0].frequency"],
                         "Every Pay")

    def test_empty_array_and_missing_entry(self):
        self.assertEqual(deposits_of(self.output, IDS[4]), [])
        self.assertEqual(deposits_of(self.output, IDS[5]), [])
        missing = issues_with(self.output, "missing_section", "direct_deposits")
        self.assertEqual([(i["record_key"], i["severity"]) for i in missing],
                         [(f"isolved:4046-5806:{IDS[5]}", "info")])

    def test_captured_ids_outside_the_pages_are_still_emitted(self):
        data = copy.deepcopy(raw_bundle("isolved", "direct-deposit"))
        data["responses"]["direct_deposits"]["999999"] = data["responses"]["direct_deposits"][IDS[0]]
        output = isolved.normalize_direct_deposits(parse_bundle(data, entity="direct-deposit")).to_dict()
        self.assertEqual(output["direct_deposits"][-1]["employee_key"], "isolved:4046-5806:999999")

    def test_account_numbers_are_reduced_to_last_four(self):
        raw = self.bundle.responses["direct_deposits"][IDS[1]][0]["accountNumber"]
        self.assertEqual(deposit_by_id(self.output, "640102")["account_number_last4"], raw[-4:])
        text = json.dumps(self.output)
        for lines in self.bundle.responses["direct_deposits"].values():
            for line in lines:
                self.assertNotIn(line["accountNumber"], text)


if __name__ == "__main__":
    unittest.main()
