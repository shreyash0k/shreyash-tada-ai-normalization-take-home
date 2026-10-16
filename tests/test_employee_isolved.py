"""isolved employee adapter: golden output plus the injected edge cases."""
import unittest

from _fixtures import employee_by_source_id, expected_output, fixture_bundle, issues_with
from normalization.adapters import isolved


class IsolvedEmployeeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("isolved")
        cls.output = isolved.normalize_employees(cls.bundle).to_dict()

    def employee(self, employee_id):
        return employee_by_source_id(self.output, str(employee_id))

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("isolved"))

    def test_is_deterministic(self):
        self.assertEqual(isolved.normalize_employees(self.bundle).to_dict(), self.output)

    def test_company_key_combines_client_and_legal(self):
        self.assertEqual(self.output["company"]["key"], "isolved:4046-5806")
        self.assertEqual(self.output["company"]["source"]["secondary_ids"], {"legalCode": "BK422-1"})
        self.assertIsNone(self.output["company"]["name"])
        self.assertEqual(len(self.output["employees"]), 6)
        self.assertEqual(self.employee(859201)["key"], "isolved:4046-5806:859201")

    def test_pages_are_concatenated_in_order(self):
        ids = [e["source"]["employee_id"] for e in self.output["employees"]]
        self.assertEqual(ids, [str(i) for i in range(859201, 859207)])

    def test_allowlisted_labels_map(self):
        self.assertEqual(self.employee(859201)["employment"]["status"]["value"], "active")
        self.assertEqual(self.employee(859203)["employment"]["status"]["value"], "terminated")
        self.assertEqual(self.employee(859201)["person"]["gender"]["value"], "male")
        self.assertEqual(self.employee(859202)["person"]["gender"]["value"], "female")
        self.assertEqual(self.employee(859201)["compensation"]["pay_type"]["value"], "salary")
        self.assertEqual(self.employee(859202)["compensation"]["pay_type"]["value"], "hourly")
        self.assertEqual(self.employee(859205)["compensation"]["pay_type"]["value"], "contractor_1099")

    def test_off_allowlist_labels_stay_raw_with_issue(self):
        odd = self.employee(859204)
        self.assertEqual(odd["employment"]["status"], {"raw": "Leave of Absence", "label": None, "value": "unknown"})
        self.assertEqual(odd["person"]["gender"]["value"], "unknown")
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "unmapped_label", "employmentStatus")],
                         [odd["key"]])
        self.assertEqual([i["raw_value"] for i in issues_with(self.output, "unmapped_label", "gender")],
                         ["Non-binary"])

    def test_descriptions_without_allowlist_are_unknown(self):
        married = self.employee(859201)
        self.assertEqual(married["person"]["marital_status"], {"raw": "Married", "label": None, "value": "unknown"})
        self.assertEqual(married["person"]["citizenship"]["value"], "unknown")
        self.assertTrue(issues_with(self.output, "unmapped_label", "maritalStatus"))
        self.assertEqual(married["person"]["ethnicity"]["value"], None)

    def test_client_codes_and_integer_frequency_are_undocumented(self):
        part_time = self.employee(859204)
        self.assertEqual(part_time["employment"]["employment_type"], {"raw": "PT", "label": None, "value": "unknown"})
        self.assertEqual(part_time["compensation"]["pay_frequency"],
                         {"raw": 12, "label": "Monthly", "value": "unknown"})
        self.assertEqual(len(issues_with(self.output, "undocumented_code", "employmentCategoryCode")), 6)
        self.assertEqual(len(issues_with(self.output, "undocumented_code", "payFrequency")), 6)

    def test_invalid_date_is_reported_and_nulled(self):
        bad = self.employee(859205)
        self.assertIsNone(bad["compensation"]["effective_date"])
        found = issues_with(self.output, "invalid_date", "salaryEffectiveDate")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(bad["key"], "not-a-date")])

    def test_iso_datetime_strings_become_dates(self):
        terminated = self.employee(859203)
        self.assertEqual(terminated["employment"]["termination_date"], "2024-03-29")
        self.assertEqual(terminated["employment"]["status_date"], "2024-03-29")
        self.assertIs(terminated["employment"]["rehire_eligible"], False)
        self.assertEqual(terminated["employment"]["termination_reason"]["raw"], "Retirement")
        self.assertEqual(self.employee(859205)["employment"]["rehire_date"], "2023-01-09")

    def test_ssn_is_reduced_to_last_four(self):
        raw = self.bundle.responses["employees"][0]["results"][2]["ssn"]
        self.assertEqual(self.employee(859203)["person"]["ssn_last4"], raw[-4:])
        self.assertNotIn(raw, str(self.output))
        self.assertIsNone(self.employee(859201)["person"]["ssn_last4"])

    def test_detail_overlay_supplies_organizations_and_taxes(self):
        detailed = self.employee(859201)
        self.assertEqual(detailed["job"]["department"], {"raw": "100", "label": "Executives", "value": None})
        self.assertEqual(detailed["job"]["location"],
                         {"raw": "UT1", "label": "UT1 - SALT LAKE CITY, UT", "value": None})
        self.assertEqual(detailed["unmapped"]["organizations[0].title"], "Location")
        self.assertEqual(detailed["unmapped"]["organizations[0].value"], "10")
        self.assertIn("taxes.federal.filingStatus", detailed["unmapped"])
        self.assertIn("organizations[0].organizationId", detailed["unmapped"])
        plain = self.employee(859202)
        self.assertEqual(plain["job"]["location"], {"raw": "UT1", "label": "UT1 - SALT LAKE CITY, UT", "value": None})
        self.assertIsNone(plain["job"]["department"])

    def test_personal_and_name_address_overrides(self):
        overridden = self.employee(859202)
        self.assertEqual(overridden["person"]["preferred_name"], "Jo")
        self.assertEqual([p["kind"] for p in overridden["contact"]["phones"]], ["mobile", "work", "other"])
        self.assertEqual(overridden["contact"]["phones"][2]["number"], "(801) 555-0142")
        self.assertNotIn("personal.faxNumber", overridden["unmapped"])
        self.assertEqual([e["kind"] for e in overridden["contact"]["emails"]], ["unknown", "personal"])
        self.assertEqual(overridden["job"]["manager_employee_id"], "859201")

    def test_sparse_record_has_nulls_and_no_extra_issues(self):
        sparse = self.employee(859206)
        self.assertIsNone(sparse["person"]["citizenship"])
        self.assertIsNone(sparse["job"]["manager_employee_id"])
        self.assertNotIn("acaEmploymentStatus", sparse["unmapped"])
        self.assertFalse(issues_with(self.output, "missing_section", "nameAddress"))

    def test_compensation_values_are_copied_not_derived(self):
        hourly = self.employee(859202)["compensation"]
        self.assertIsNone(hourly["rate"])
        self.assertIsNotNone(hourly["hourly_rate"])
        self.assertEqual(hourly["standard_hours"], "173.33")
        self.assertEqual(hourly["standard_hours_period"]["value"], "pay_period")


if __name__ == "__main__":
    unittest.main()
