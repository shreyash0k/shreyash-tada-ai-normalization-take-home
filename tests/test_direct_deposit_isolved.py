"""isolved direct deposit adapter."""
import copy
import json
import unittest

from _fixtures import (
    deposit_by_id,
    expected_output,
    fixture_bundle,
    issues_with,
    raw_bundle,
    resolve_code_table,
)
from normalization.adapters import isolved
from normalization.bundle import parse_bundle

IDS = [str(859201 + i) for i in range(8)]


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
        self.assertEqual(len(self.output["direct_deposits"]), 9)
        for deposit in self.output["direct_deposits"]:
            with self.subTest(key=deposit["key"]):
                self.assertIn(deposit["employee_key"], employee_keys)
                self.assertEqual(deposit["key"], f"{deposit['employee_key']}:dd:{deposit['source']['deposit_id']}")
        self.assertEqual(self.output["company"]["key"], "isolved:4046-5806")
        self.assertEqual(self.output["company"]["source"]["secondary_ids"], {"legalCode": "BK422-1"})

    def test_amount_and_percent_follow_the_field_that_is_set(self):
        fixed = deposit_by_id(self.output, "640200")
        self.assertEqual(fixed["allocation"]["method"]["value"], "fixed_amount")
        self.assertIsNotNone(fixed["allocation"]["amount"])
        self.assertEqual(fixed["priority"], 1)
        self.assertEqual(fixed["account_type"]["value"], "checking")
        percent = deposit_by_id(self.output, "640300")
        self.assertEqual(percent["allocation"]["method"]["value"], "percent")
        self.assertEqual(percent["allocation"]["percent"], "10.0")

    def test_pending_status_stays_raw(self):
        pending = deposit_by_id(self.output, "640207")
        self.assertEqual(pending["status"]["value"], "unknown")
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "unmapped_label")], ["Pending"])
        self.assertEqual(pending["employee_key"], f"isolved:4046-5806:{IDS[7]}")

    def test_label_tables_point_at_free_text_fields(self):
        for table in (isolved.DEPOSIT_ACCOUNT_TYPE, isolved.DEPOSIT_STATUS):
            with self.subTest(table=table.name):
                field = resolve_code_table(table)
                self.assertEqual(field["type"], "string")
                self.assertNotIn("enum", field)
                self.assertEqual(table.kind, "label")

    def test_frequency_stays_unmapped(self):
        self.assertEqual(deposit_by_id(self.output, "640200")["unmapped"]["direct_deposits[0].frequency"],
                         "Every Pay")

    def test_captured_ids_outside_the_pages_are_still_emitted(self):
        data = copy.deepcopy(raw_bundle("isolved", "direct-deposit"))
        data["responses"]["direct_deposits"]["999999"] = data["responses"]["direct_deposits"][IDS[0]]
        output = isolved.normalize_direct_deposits(parse_bundle(data, entity="direct-deposit")).to_dict()
        self.assertEqual(output["direct_deposits"][-1]["employee_key"], "isolved:4046-5806:999999")

    def test_account_numbers_are_reduced_to_last_four(self):
        raw = self.bundle.responses["direct_deposits"][IDS[1]][0]["accountNumber"]
        self.assertEqual(deposit_by_id(self.output, "640201")["account_number_last4"], raw[-4:])
        text = json.dumps(self.output)
        for lines in self.bundle.responses["direct_deposits"].values():
            for line in lines:
                self.assertNotIn(line["accountNumber"], text)


if __name__ == "__main__":
    unittest.main()
