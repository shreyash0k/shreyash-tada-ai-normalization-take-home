"""UKG Ready company adapter: golden output plus the injected edge cases."""
import copy
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, raw_bundle, resolve_code_table
from normalization.adapters import ukg_ready
from normalization.bundle import parse_bundle

COMPANY = "ukg-ready:33704016"
SECOND_EIN = {"id": 35419521, "ein_name": "2nd EIN", "ein_tax_id": "22-3456789", "ein_country_id": "USA"}


def normalize_variant(change):
    raw = copy.deepcopy(raw_bundle("ukg-ready", "company"))
    change(raw["responses"])
    return ukg_ready.normalize_company(parse_bundle(raw, entity="company")).to_dict()


class UkgCompanyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("ukg-ready", "company")
        cls.output = ukg_ready.normalize_company(cls.bundle).to_dict()
        cls.company = cls.output["company"]

    def frequency(self, profile_id):
        return next(g["frequency"] for g in self.company["pay_groups"] if g["source_id"] == profile_id)

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("ukg-ready", "company"))

    def test_is_deterministic(self):
        self.assertEqual(ukg_ready.normalize_company(self.bundle).to_dict(), self.output)

    def test_profile_is_empty_with_an_issue(self):
        company = self.company
        self.assertEqual(company["key"], COMPANY)
        for field in ("name", "legal_name", "status", "address", "phone"):
            with self.subTest(field=field):
                self.assertIsNone(company[field])
        found = issues_with(self.output, "missing_section")
        self.assertEqual([i["severity"] for i in found], ["warning", "info"])

    def test_no_work_locations(self):
        self.assertEqual(self.company["work_locations"], [])
        self.assertIn("work locations", issues_with(self.output, "missing_section")[1]["action"])

    def test_single_ein(self):
        self.assertEqual(self.company["ein"], "12-3456789")
        self.assertEqual(self.company["tax_ids"], [{
            "key": f"{COMPANY}:ein:35419520", "source_id": "35419520", "tax_id": "12-3456789",
            "name": "Primary EIN", "country": "USA",
            "unmapped": {"lookup_eins.items[0].ein_currency_code": "USD"}}])

    def test_two_eins_list_both_and_leave_ein_null(self):
        output = normalize_variant(lambda r: r["lookup_eins"]["items"].append(SECOND_EIN))
        self.assertIsNone(output["company"]["ein"])
        self.assertEqual([t["source_id"] for t in output["company"]["tax_ids"]], ["35419520", "35419521"])
        found = issues_with(output, "missing_lookup")
        self.assertEqual([(i["raw_value"], i["severity"]) for i in found], [(2, "warning")])

    def test_frequency_mapping(self):
        expected = {"36562688": "biweekly", "36562692": "weekly", "36562698": "semimonthly",
                    "36562689": "monthly", "36562700": "unknown", "36562701": "unknown", "36562702": "unknown",
                    "36562703": "unknown", "36562699": "unknown", "36562704": "unknown"}
        for profile_id, value in expected.items():
            with self.subTest(profile=profile_id):
                self.assertEqual(self.frequency(profile_id)["value"], value)
        self.assertEqual(self.frequency("36562688")["label"], "every_n_weeks")

    def test_one_week_cycle_is_weekly(self):
        def one_week(responses):
            responses["lookup_pay_period_profiles"]["items"][0]["period_type"]["params"]["num_weeks"] = 1
        output = normalize_variant(one_week)
        self.assertEqual(output["company"]["pay_groups"][0]["frequency"]["value"], "weekly")

    def test_out_of_enum_period_type(self):
        found = issues_with(self.output, "out_of_schema_value")
        self.assertEqual([(i["raw_value"], i["record_key"]) for i in found],
                         [("fortnightly", f"{COMPANY}:pg:36562704")])

    def test_profile_fields(self):
        groups = {g["source_id"]: g for g in self.company["pay_groups"]}
        first = groups["36562688"]
        self.assertEqual(first["code"], {"raw": "36562688", "label": "Primary-EIN Regular Bi-Weekly", "value": None})
        self.assertIs(first["active"], True)
        self.assertEqual(first["effective"], {"start": "2018-01-21", "end": None})
        self.assertEqual(first["unmapped"]["lookup_pay_period_profiles.items[0].description"], "Primary EIN payroll")
        self.assertEqual(groups["36562699"]["effective"], {"start": "2023-05-01", "end": "2023-10-01"})

    def test_missing_profiles_leave_pay_groups_empty(self):
        output = normalize_variant(lambda r: r.pop("lookup_pay_period_profiles"))
        self.assertEqual(output["company"]["pay_groups"], [])

    def test_code_tables_quote_the_spec_descriptions(self):
        self.assertEqual(sorted(ukg_ready.PERIOD_TYPE.entries), sorted(resolve_code_table(ukg_ready.PERIOD_TYPE)["enum"]))


if __name__ == "__main__":
    unittest.main()
