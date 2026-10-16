"""PrismHR employee adapter: golden output plus the injected edge cases."""
import copy
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with
from normalization.adapters import prismhr


def by_client_employee_id(output, number):
    for employee in output["employees"]:
        if employee["source"]["secondary_ids"].get("clientEmployeeId") == str(number):
            return employee
    raise KeyError(number)


class PrismHREmployeeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("prismhr")
        cls.output = prismhr.normalize_employees(cls.bundle).to_dict()

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("prismhr"))

    def test_is_deterministic(self):
        self.assertEqual(prismhr.normalize_employees(self.bundle).to_dict(), self.output)

    def test_keys_and_company_link(self):
        self.assertEqual(self.output["company"]["key"], "prismhr:132")
        self.assertIsNone(self.output["company"]["name"])
        self.assertEqual(len(self.output["employees"]), 7)
        for employee in self.output["employees"]:
            self.assertEqual(employee["company_key"], "prismhr:132")
            self.assertEqual(employee["key"], f"prismhr:132:{employee['source']['employee_id']}")

    def test_documented_codes_map_to_canonical_values(self):
        on_leave = by_client_employee_id(self.output, 3)
        self.assertEqual(on_leave["employment"]["status"], {"raw": "L", "label": "LOA", "value": "on_leave"})
        self.assertEqual(on_leave["employment"]["employment_type"]["value"], "part_time")
        self.assertEqual(on_leave["compensation"]["pay_type"]["value"], "hourly")
        self.assertEqual(on_leave["compensation"]["rate_period"]["value"], "hourly")
        terminated = by_client_employee_id(self.output, 4)
        self.assertEqual(terminated["employment"]["status"]["value"], "terminated")
        self.assertIs(terminated["employment"]["rehire_eligible"], False)
        self.assertEqual(terminated["employment"]["termination_reason"],
                         {"raw": "RES", "label": "Resigned", "value": None})
        driver = by_client_employee_id(self.output, 7)
        self.assertEqual(driver["compensation"]["pay_type"]["value"], "driver")
        self.assertIs(driver["employment"]["contractor_1099"], True)

    def test_undocumented_status_class_stays_raw(self):
        odd = by_client_employee_id(self.output, 5)
        self.assertEqual(odd["employment"]["status"], {"raw": "Q", "label": "Q", "value": "unknown"})
        found = issues_with(self.output, "undocumented_code", "client.statusClass")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["record_key"], odd["key"])
        self.assertEqual(found[0]["raw_value"], "Q")

    def test_pay_period_uses_the_pay_group_schedule_codes(self):
        frequencies = {(e["compensation"]["pay_frequency"]["raw"], e["compensation"]["pay_frequency"]["value"])
                       for e in self.output["employees"]}
        self.assertEqual(frequencies, {("W", "weekly"), ("B", "biweekly"), ("S", "semimonthly"),
                                       ("M", "monthly")})
        self.assertEqual(issues_with(self.output, "undocumented_code", "compensation.payPeriod"), [])

    def test_pay_period_off_the_schedule_list_is_undocumented(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses["get_employee"][0]["employee"][0]["compensation"]["payPeriod"] = "Q"
        output = prismhr.normalize_employees(bundle).to_dict()
        found = issues_with(output, "undocumented_code", "compensation.payPeriod")
        self.assertEqual([i["raw_value"] for i in found], ["Q"])
        self.assertEqual(by_client_employee_id(output, 1)["compensation"]["pay_frequency"]["value"], "unknown")

    def test_job_titles_come_from_the_job_table(self):
        titles = {(e["job"]["job_code"]["raw"], e["job"]["title"]) for e in self.output["employees"]}
        self.assertEqual(titles, {("WHSE", "Warehouse Associate"), ("OFFICE", "Office Staff"), ("TECH", None)})
        found = issues_with(self.output, "missing_lookup", "client.jobCode")
        tech = [e["key"] for e in self.output["employees"] if e["job"]["job_code"]["raw"] == "TECH"]
        self.assertEqual([i["record_key"] for i in found], tech)
        self.assertEqual({i["raw_value"] for i in found}, {"TECH"})

    def test_job_table_is_optional(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.responses.pop("get_client_codes_job")
        output = prismhr.normalize_employees(bundle).to_dict()
        found = issues_with(output, "missing_section", "get_client_codes_job")
        self.assertEqual([(i["severity"], i["record_key"]) for i in found], [("info", None)])
        self.assertEqual({e["job"]["title"] for e in output["employees"]}, {None})
        self.assertFalse(issues_with(output, "missing_lookup", "client.jobCode"))

    def test_masked_ssn_becomes_null_with_issue(self):
        masked = by_client_employee_id(self.output, 2)
        self.assertIsNone(masked["person"]["ssn_last4"])
        found = issues_with(self.output, "masked_value", "compensation.ssn")
        self.assertEqual([i["record_key"] for i in found], [masked["key"]])
        self.assertEqual(found[0]["raw_value"], "[redacted]")

    def test_only_last_four_ssn_digits_are_emitted(self):
        raw_ssn = self.bundle.responses["get_employee"][0]["employee"][0]["compensation"]["ssn"]
        first = by_client_employee_id(self.output, 1)
        self.assertEqual(first["person"]["ssn_last4"], raw_ssn[-4:])
        self.assertNotIn(raw_ssn, str(self.output))

    def test_invalid_date_is_reported_and_nulled(self):
        bad = by_client_employee_id(self.output, 6)
        self.assertIsNone(bad["person"]["birth_date"])
        found = issues_with(self.output, "invalid_date", "person.birthDate")
        self.assertEqual(found[0]["raw_value"], "2001-02-30")
        self.assertEqual(found[0]["severity"], "error")

    def test_prose_citizenship_is_unmapped_label(self):
        prose = by_client_employee_id(self.output, 4)
        self.assertEqual(prose["person"]["citizenship"]["value"], "unknown")
        self.assertEqual(prose["person"]["citizenship"]["raw"], "A lawful permanent resident")
        self.assertEqual(len(issues_with(self.output, "unmapped_label", "citizenshipStatus")), 1)
        documented = by_client_employee_id(self.output, 1)
        self.assertEqual(documented["person"]["citizenship"]["value"], "citizen")

    def test_live_spellings_reported_once_per_bundle(self):
        paths = sorted(i["source_path"] for i in issues_with(self.output, "spec_live_mismatch"))
        self.assertEqual(paths, ["client.hawaiiMedWaiver", "compensation.payPeriodsPerWeek",
                                 "person.autoPolicy", "person.employerId"])
        self.assertIn("person.employerId", by_client_employee_id(self.output, 1)["unmapped"])

    def test_addresses_phones_and_manager(self):
        first = by_client_employee_id(self.output, 1)
        kinds = [a["kind"] for a in first["contact"]["addresses"]]
        self.assertEqual(kinds, ["home", "mailing"])
        mailing = first["contact"]["addresses"][1]
        self.assertEqual((mailing["line1"], mailing["postal_code"], mailing["country"]),
                         ("PO Box 410", "63105-1234", "USA"))
        self.assertEqual([p["kind"] for p in first["contact"]["phones"]], ["home", "mobile"])
        benefit = [e["address"] for e in first["contact"]["emails"] if e["kind"] == "other"]
        self.assertEqual(len(benefit), 1)
        self.assertTrue(benefit[0].endswith(".benefits@example.test"))
        self.assertNotIn("client.benefitEmail", first["unmapped"])
        second = by_client_employee_id(self.output, 2)
        self.assertEqual(second["job"]["manager_employee_id"], first["source"]["employee_id"])

    def test_compensation_fields_are_not_derived(self):
        hourly = by_client_employee_id(self.output, 2)
        comp = hourly["compensation"]
        self.assertEqual(comp["hourly_rate"]["amount"], comp["rate"]["amount"])
        self.assertEqual(comp["standard_hours"], "40.00")
        self.assertEqual(comp["standard_hours_period"]["value"], "pay_period")
        self.assertIsNotNone(comp["effective_date"])

    def test_unmapped_keeps_unconsumed_fields_and_redacts_identifiers(self):
        first = by_client_employee_id(self.output, 1)
        self.assertIn("person.ohioFormC112", first["unmapped"])
        self.assertIn("compensation.fedFilingStatus", first["unmapped"])
        self.assertNotIn("compensation.ssn", first["unmapped"])
        self.assertNotIn("client.statusClass", first["unmapped"])


if __name__ == "__main__":
    unittest.main()
