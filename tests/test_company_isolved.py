"""isolved company adapter: golden output plus the injected edge cases."""
import copy
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, raw_bundle, resolve_code_table
from normalization.adapters import isolved
from normalization.bundle import parse_bundle

COMPANY = "isolved:4046-5806"


def normalize_variant(change):
    raw = copy.deepcopy(raw_bundle("isolved", "company"))
    change(raw["responses"]["legal"])
    return isolved.normalize_company(parse_bundle(raw, entity="company")).to_dict()


class IsolvedCompanyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("isolved", "company")
        cls.output = isolved.normalize_company(cls.bundle).to_dict()
        cls.company = cls.output["company"]

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("isolved", "company"))

    def test_is_deterministic(self):
        self.assertEqual(isolved.normalize_company(self.bundle).to_dict(), self.output)

    def test_profile_fields(self):
        company = self.company
        self.assertEqual(company["key"], COMPANY)
        self.assertEqual(company["legal_name"], "Dunder Mifflin Stamford, Inc.")
        self.assertEqual(company["status"], {"raw": "Active", "label": None, "value": "active"})
        self.assertEqual(company["address"]["kind"], "legal")
        self.assertEqual(company["phone"]["kind"], "work")
        self.assertEqual(company["ein"], "990004046")
        self.assertEqual([(t["key"], t["source_id"]) for t in company["tax_ids"]],
                         [(f"{COMPANY}:ein:990004046", None)])

    def test_name_is_null_without_a_dba_name(self):
        self.assertIsNone(self.company["name"])
        self.assertIsNotNone(self.company["legal_name"])
        found = issues_with(self.output, "missing_section", "dbaName")
        self.assertEqual([(i["record_key"], i["severity"]) for i in found], [(COMPANY, "info")])
        named = normalize_variant(lambda legal: legal.update(dbaName="Synthetic Scrap"))
        self.assertEqual(named["company"]["name"], "Synthetic Scrap")
        self.assertEqual(issues_with(named, "missing_section", "dbaName"), [])

    def test_parent_and_secondary_ids(self):
        self.assertEqual(self.company["parent"], {"raw": "4046", "label": "Dunder Mifflin", "value": None})
        self.assertEqual(self.company["source"]["secondary_ids"], {"legalCode": "SYN42-1", "clientCode": "SYN42"})

    def test_services_and_workers_comp_stay_in_unmapped(self):
        unmapped = self.company["unmapped"]
        self.assertEqual(unmapped["services[0].code"], "BASE")
        self.assertEqual(unmapped["workersComps[0].code"], "8810")
        self.assertNotIn("workLocations[0].id", unmapped)
        self.assertNotIn("payGroups[0].id", unmapped)

    def test_unlisted_status_label(self):
        output = normalize_variant(lambda legal: legal.update(status="Terminated"))
        self.assertEqual(output["company"]["status"], {"raw": "Terminated", "label": None, "value": "unknown"})
        self.assertEqual([i["source_path"] for i in issues_with(output, "unmapped_label")], ["status"])

    def test_legal_without_details(self):
        def strip(legal):
            for name in isolved.LEGAL_DETAIL_KEYS:
                legal.pop(name)
        output = normalize_variant(strip)
        self.assertIsNone(output["company"]["address"])
        self.assertEqual(output["company"]["work_locations"], [])
        self.assertEqual(len(output["company"]["pay_groups"]), 2)
        found = issues_with(output, "missing_section", "legal")
        self.assertEqual([i["severity"] for i in found], ["info"])
        self.assertEqual(issues_with(self.output, "missing_section", "legal"), [])

    def test_work_locations(self):
        locations = self.company["work_locations"]
        self.assertEqual([(w["source_id"], w["code"]["raw"], w["active"]) for w in locations],
                         [("25721", "UT1", True), ("25722", "UT2", False)])
        self.assertEqual(locations[0]["key"], f"{COMPANY}:loc:25721")
        self.assertEqual(locations[0]["code"]["label"], "SALT LAKE CITY, UT")
        self.assertEqual(locations[0]["address"]["kind"], "work")
        self.assertIs(locations[0]["remote"], False)
        self.assertEqual(locations[0]["unmapped"]["workLocations[0].timeZone"], "Mountain Standard Time")

    def test_pay_groups(self):
        groups = self.company["pay_groups"]
        self.assertEqual([(g["source_id"], g["active"]) for g in groups], [("7627", True), ("7628", False)])
        self.assertEqual(groups[0]["code"], {"raw": "7627", "label": "Monthly", "value": None})
        self.assertEqual(groups[0]["frequency"], {"raw": 12, "label": "Monthly", "value": "unknown"})
        found = issues_with(self.output, "undocumented_code", "payFrequency")
        self.assertEqual([i["raw_value"] for i in found], [12, 52])

    def test_code_tables_quote_the_spec_descriptions(self):
        self.assertEqual(resolve_code_table(isolved.COMPANY_STATUS)["description"], "Current Legal Company Status")
        self.assertEqual(resolve_code_table(isolved.GROUP_PAY_FREQUENCY)["type"], "integer")


if __name__ == "__main__":
    unittest.main()
