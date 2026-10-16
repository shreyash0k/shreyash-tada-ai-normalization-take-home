"""UKG Ready employee adapter: golden output plus the injected edge cases."""
import copy
import unittest

from _fixtures import employee_by_source_id, expected_output, fixture_bundle, issues_with
from normalization.adapters import ukg_ready

IDS = [str(12935181566 + i) for i in range(6)]


class UkgReadyEmployeeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("ukg-ready")
        cls.output = ukg_ready.normalize_employees(cls.bundle).to_dict()

    def employee(self, index):
        return employee_by_source_id(self.output, IDS[index])

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("ukg-ready"))

    def test_is_deterministic(self):
        self.assertEqual(ukg_ready.normalize_employees(self.bundle).to_dict(), self.output)

    def test_company_stub_takes_ein_from_single_lookup_row(self):
        company = self.output["company"]
        self.assertEqual(company["key"], "ukg-ready:33704016")
        self.assertEqual(company["ein"], "12-3456789")
        self.assertEqual(company["source"]["secondary_ids"], {"ein_name": "Primary EIN"})
        self.assertIsNone(company["name"])
        self.assertEqual(len(self.output["employees"]), 6)

    def test_status_allowlist(self):
        self.assertEqual(self.employee(0)["employment"]["status"]["value"], "active")
        self.assertEqual(self.employee(2)["employment"]["status"]["value"], "terminated")
        suspended = self.employee(4)
        self.assertEqual(suspended["employment"]["status"], {"raw": "Suspended", "label": None, "value": "unknown"})
        self.assertEqual([i["record_key"] for i in issues_with(self.output, "unmapped_label", "status")],
                         [suspended["key"]])

    def test_schema_enums_map_directly(self):
        self.assertEqual(self.employee(0)["person"]["gender"]["value"], "male")
        self.assertEqual(self.employee(1)["person"]["gender"]["value"], "female")
        undefined = self.employee(4)["person"]["gender"]
        self.assertEqual(undefined, {"raw": "UNDEFINED", "label": None, "value": "unknown"})
        self.assertFalse(issues_with(self.output, "undocumented_code", "demographics.gender"))
        self.assertIn(self.employee(0)["person"]["citizenship"]["value"],
                      {"citizen", "permanent_resident", "work_permit"})
        self.assertIsNone(self.employee(0)["person"]["ethnicity"]["value"])

    def test_missing_demographics_section(self):
        missing = self.employee(3)
        self.assertIsNone(missing["person"]["gender"])
        self.assertIsNone(missing["person"]["citizenship"])
        found = issues_with(self.output, "missing_section", "demographics")
        self.assertEqual([i["record_key"] for i in found], [missing["key"]])

    def test_tenant_lookups_resolve_to_labels_but_stay_unknown(self):
        first = self.employee(0)
        self.assertEqual(first["employment"]["employment_type"],
                         {"raw": 35330178, "label": "FT Exempt", "value": "unknown"})
        self.assertEqual(first["compensation"]["pay_type"],
                         {"raw": 35043009, "label": "Salaried", "value": "unknown"})
        self.assertTrue(issues_with(self.output, "unmapped_label", "pay_info.employee_type.id"))
        self.assertTrue(issues_with(self.output, "unmapped_label", "pay_info.pay_type.id"))

    def test_lookup_miss_is_reported(self):
        orphan = self.employee(4)
        self.assertEqual(orphan["employment"]["employment_type"], {"raw": 99999999, "label": None, "value": "unknown"})
        found = issues_with(self.output, "missing_lookup", "pay_info.employee_type.id")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(orphan["key"], 99999999)])

    def test_job_titles_come_from_the_jobs_lookup(self):
        self.assertEqual(self.employee(0)["job"]["title"], "President")
        self.assertEqual(self.employee(0)["job"]["job_code"], {"raw": 8634524226, "label": None, "value": None})
        self.assertIsNone(self.employee(3)["job"]["title"])
        orphan = self.employee(4)
        self.assertIsNone(orphan["job"]["title"])
        found = issues_with(self.output, "missing_lookup", "pay_info.default_job.id")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(orphan["key"], 8634529999)])

    def test_contractor_flag_comes_from_tax_info(self):
        self.assertEqual([self.employee(i)["employment"]["contractor_1099"] for i in range(6)],
                         [False, False, True, False, False, None])
        self.assertIs(self.employee(0)["unmapped"]["tax_info.employee-tax-type.W2"], True)
        self.assertEqual(self.employee(0)["unmapped"]["tax_info.third-party-sick"], "COMPANY_DEFAULT")
        found = issues_with(self.output, "missing_section", "tax_info")
        self.assertEqual([(i["record_key"], i["severity"]) for i in found], [(self.employee(5)["key"], "info")])

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

    def test_current_compensation_skips_placeholder_and_future_rows(self):
        comp = self.employee(0)["compensation"]
        self.assertEqual(comp["effective_date"], "2026-01-01")
        self.assertEqual(comp["rate_period"]["value"], "annual")
        self.assertEqual(comp["annual_amount"], comp["rate"])
        self.assertIsNone(comp["per_period_amount"])
        self.assertEqual(comp["standard_hours"], "2080.00")
        self.assertEqual(comp["standard_hours_period"]["value"], "annual")
        self.assertEqual(comp["standard_work_day_hours"], "0.00")
        self.assertIn("compensation_history.compensations[2].effective_from", self.employee(0)["unmapped"])

    def test_zero_pay_periods_is_out_of_schema(self):
        found = issues_with(self.output, "out_of_schema_value", "num_pp_in_year")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(self.employee(0)["key"], 0)])

    def test_tied_effective_dates_report_multiple_current_rates(self):
        tied = self.employee(3)
        self.assertEqual(tied["compensation"]["rate"]["amount"], "2400.0")
        self.assertEqual(tied["compensation"]["per_period_amount"]["amount"], "2400.0")
        self.assertEqual(tied["compensation"]["standard_hours"], "80.00")
        found = issues_with(self.output, "multiple_current_rates")
        self.assertEqual([i["record_key"] for i in found], [tied["key"]])

    def test_empty_history_leaves_compensation_null(self):
        comp = self.employee(5)["compensation"]
        self.assertIsNone(comp["rate"])
        self.assertIsNone(comp["effective_date"])
        self.assertIsNotNone(comp["pay_type"])
        self.assertEqual(comp["standard_work_day_hours"], "8.00")

    def test_eeo4_unknown_is_out_of_schema(self):
        found = issues_with(self.output, "out_of_schema_value", "eeo4_")
        self.assertEqual(sorted(i["source_path"] for i in found),
                         ["pay_info.eeo4_classification", "pay_info.eeo4_function"])
        self.assertEqual({i["record_key"] for i in found}, {self.employee(1)["key"]})
        self.assertFalse(issues_with(self.output, "out_of_schema_value", "PROFESSIONALS"))

    def test_invalid_seniority_date(self):
        found = issues_with(self.output, "invalid_date", "dates.seniority")
        self.assertEqual([(i["record_key"], i["raw_value"]) for i in found], [(self.employee(5)["key"], "2020-13-01")])
        self.assertIsNone(self.employee(5)["employment"]["seniority_date"])

    def test_dates_and_manager(self):
        self.assertEqual(self.employee(2)["employment"]["termination_date"], "2024-06-28")
        self.assertEqual(self.employee(3)["employment"]["rehire_date"], "2022-02-14")
        self.assertEqual(self.employee(3)["job"]["manager_employee_id"], IDS[1])
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
