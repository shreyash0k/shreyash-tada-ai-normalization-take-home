"""UKG Ready employee adapter: golden output plus the injected edge cases."""
import copy
import unittest

from _fixtures import employee_by_source_id, expected_output, fixture_bundle, issues_with
from normalization.adapters import ukg_ready

IDS = [str(12935181566 + i) for i in range(8)]


class UkgReadyEmployeeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("ukg-ready")
        cls.output = ukg_ready.normalize_employees(cls.bundle).to_dict()

    def employee(self, index):
        return employee_by_source_id(self.output, IDS[index])

    @staticmethod
    def employee_in(output, index):
        return employee_by_source_id(output, IDS[index])

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("ukg-ready"))

    def test_is_deterministic(self):
        self.assertEqual(ukg_ready.normalize_employees(self.bundle).to_dict(), self.output)

    def test_company_stub_takes_ein_from_single_lookup_row(self):
        company = self.output["company"]
        self.assertEqual(company["key"], "ukg-ready:33704016")
        self.assertEqual(company["ein"], "12-3456789")
        self.assertEqual(company["source"]["secondary_ids"], {"ein_name": "Dunder Mifflin Utica"})
        self.assertIsNone(company["name"])
        self.assertEqual(len(self.output["employees"]), 8)

    def test_status_allowlist(self):
        self.assertEqual(self.employee(0)["employment"]["status"]["value"], "active")
        self.assertEqual(self.employee(7)["employment"]["status"]["value"], "terminated")
        self.assertEqual(issues_with(self.output, "unmapped_label", "status"), [])

    def test_schema_enums_map_directly(self):
        self.assertEqual(self.employee(0)["person"]["gender"]["value"], "male")
        self.assertEqual(self.employee(1)["person"]["gender"]["value"], "female")
        self.assertFalse(issues_with(self.output, "undocumented_code", "demographics.gender"))
        self.assertIn(self.employee(0)["person"]["citizenship"]["value"],
                      {"citizen", "permanent_resident", "work_permit"})
        self.assertIsNone(self.employee(0)["person"]["ethnicity"]["value"])

    def test_tenant_lookups_resolve_to_labels_but_stay_unknown(self):
        first = self.employee(0)
        self.assertEqual(first["employment"]["employment_type"],
                         {"raw": 35330178, "label": "FT Exempt", "value": "unknown"})
        self.assertEqual(first["compensation"]["pay_type"],
                         {"raw": 35043009, "label": "Salaried", "value": "unknown"})
        self.assertEqual(len(issues_with(self.output, "unmapped_label", "pay_info.employee_type.id")), 1)
        self.assertEqual(len(issues_with(self.output, "unmapped_label", "pay_info.pay_type.id")), 1)

    def test_job_titles_come_from_the_jobs_lookup(self):
        self.assertEqual(self.employee(0)["job"]["title"], "Regional Manager")
        self.assertEqual(self.employee(0)["job"]["job_code"], {"raw": 8634524226, "label": None, "value": None})
        self.assertEqual(self.employee(1)["job"]["title"], "Sales Representative")
        self.assertEqual(issues_with(self.output, "missing_lookup", "pay_info.default_job.id"), [])

    def test_contractor_flag_comes_from_tax_info(self):
        self.assertEqual([self.employee(i)["employment"]["contractor_1099"] for i in range(8)], [False] * 8)
        self.assertIs(self.employee(0)["unmapped"]["tax_info.employee-tax-type.W2"], True)
        self.assertEqual(self.employee(0)["unmapped"]["tax_info.third-party-sick"], "COMPANY_DEFAULT")
        self.assertEqual(issues_with(self.output, "missing_section", "tax_info"), [])

    def test_jobs_lookup_and_tax_info_are_optional(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses.pop("lookup_jobs")
        bundle.responses.pop("tax_info")
        output = ukg_ready.normalize_employees(bundle).to_dict()
        found = issues_with(output, "missing_section", "responses.")
        self.assertEqual(sorted((i["source_path"], i["severity"], i["record_key"]) for i in found),
                         [("responses.lookup_jobs", "info", None), ("responses.tax_info", "info", None)])
        self.assertEqual({e["job"]["title"] for e in output["employees"]}, {None})
        self.assertEqual({e["employment"]["contractor_1099"] for e in output["employees"]}, {None})
        self.assertFalse(issues_with(output, "missing_lookup", "default_job"))

    def test_pay_frequency_comes_from_the_pay_period_profile(self):
        self.assertEqual(self.employee(0)["compensation"]["pay_frequency"],
                         {"raw": 36562688, "label": "Primary-EIN Regular Bi-Weekly", "value": "biweekly"})
        self.assertEqual(self.employee(2)["compensation"]["pay_frequency"],
                         {"raw": 36562692, "label": "Weekly", "value": "weekly"})
        self.assertIsNone(self.employee(7)["compensation"]["pay_frequency"])
        self.assertEqual(self.employee(0)["unmapped"]["profiles.pay_period[0].effective_from"], "1900-12-31")
        self.assertEqual(issues_with(self.output, "missing_lookup", "pay_period"), [])

    def test_pay_period_profile_missing_from_lookup_stays_unknown(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses["lookup_pay_period_profiles"]["items"] = [
            p for p in bundle.responses["lookup_pay_period_profiles"]["items"] if p["id"] != 36562692]
        output = ukg_ready.normalize_employees(bundle).to_dict()
        self.assertEqual(employee_by_source_id(output, IDS[2])["compensation"]["pay_frequency"],
                         {"raw": 36562692, "label": "Weekly", "value": "unknown"})
        found = issues_with(output, "missing_lookup", "profiles.pay_period[0].id")
        self.assertEqual([(i["record_key"], i["severity"]) for i in found],
                         [(f"ukg-ready:33704016:{IDS[2]}", "warning")])

    def test_pay_period_profile_type_outside_the_schema_is_reported_once(self):
        bundle = copy.deepcopy(self.bundle)
        for profile in bundle.responses["lookup_pay_period_profiles"]["items"]:
            if profile["id"] == 36562688:
                profile["period_type"] = {"type": "fortnightly", "params": {}}
        output = ukg_ready.normalize_employees(bundle).to_dict()
        self.assertEqual(self.employee_in(output, 0)["compensation"]["pay_frequency"]["value"], "unknown")
        self.assertEqual(len(issues_with(output, "out_of_schema_value", "period_type.type")), 1)

    def test_profiles_and_pay_period_lookup_are_optional(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses.pop("profiles")
        bundle.responses.pop("lookup_pay_period_profiles")
        output = ukg_ready.normalize_employees(bundle).to_dict()
        found = issues_with(output, "missing_section", "responses.")
        self.assertEqual(sorted((i["source_path"], i["severity"]) for i in found),
                         [("responses.lookup_pay_period_profiles", "info"), ("responses.profiles", "info")])
        self.assertEqual({e["compensation"]["pay_frequency"] is None for e in output["employees"]}, {True})

    def test_current_compensation_skips_placeholder_and_future_rows(self):
        comp = self.employee(0)["compensation"]
        self.assertEqual(comp["effective_date"], "2024-01-01")
        self.assertEqual(comp["rate_period"]["value"], "annual")
        self.assertEqual(comp["annual_amount"], comp["rate"])
        self.assertIsNone(comp["per_period_amount"])
        self.assertEqual(comp["standard_hours"], "2080.00")
        self.assertEqual(comp["standard_hours_period"]["value"], "annual")
        self.assertEqual(comp["standard_work_day_hours"], "8.00")
        period = self.employee(1)["compensation"]
        self.assertEqual(period["rate_period"]["value"], "pay_period")
        self.assertIsNotNone(period["per_period_amount"])

    def test_dates_and_manager(self):
        self.assertEqual(self.employee(7)["employment"]["termination_date"], "2024-06-28")
        self.assertEqual(self.employee(7)["employment"]["rehire_date"], "2022-02-14")
        self.assertEqual(self.employee(1)["job"]["manager_employee_id"], IDS[0])
        self.assertIsNone(self.employee(0)["job"]["manager_employee_id"])

    def test_contact_details(self):
        second = self.employee(1)
        self.assertEqual([a["kind"] for a in second["contact"]["addresses"]], ["home", "mailing"])
        self.assertEqual(second["contact"]["addresses"][1]["line1"], "PO Box 77")
        phones = {p["kind"]: p["preferred"] for p in self.employee(0)["contact"]["phones"]}
        self.assertEqual(phones, {"home": False, "mobile": True})
        self.assertEqual(self.employee(0)["contact"]["emails"][0]["kind"], "unknown")

    def test_live_only_fields_reported_once(self):
        paths = sorted(i["source_path"] for i in issues_with(self.output, "spec_live_mismatch"))
        self.assertEqual(paths, ["_links.country-fields", "ein_name"])

    def test_identifiers_and_tokens_are_redacted_in_unmapped(self):
        unmapped = self.employee(0)["unmapped"]
        raw_ssn = self.bundle.responses["employee"][IDS[0]]["social_security"]
        self.assertEqual(self.employee(0)["person"]["ssn_last4"], raw_ssn[-4:])
        self.assertNotIn(raw_ssn, str(self.output))
        self.assertEqual(unmapped["national_id_numbers[0].value"], "[redacted]")
        self.assertEqual(unmapped["photo_href"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
