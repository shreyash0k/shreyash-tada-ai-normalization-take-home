"""Codes on employees and pay runs resolve against the company record's nested lists."""
import unittest

from _fixtures import ENTITIES, PROVIDERS, expected_output


def company(provider):
    return expected_output(provider, "company")["company"]


class CompanyLinkChecks(unittest.TestCase):
    def test_every_output_shares_the_company_key(self):
        for provider in PROVIDERS:
            key = company(provider)["key"]
            for entity in ENTITIES:
                with self.subTest(provider=provider, entity=entity):
                    self.assertEqual(expected_output(provider, entity)["company"]["key"], key)

    def test_prismhr_employee_locations_and_pay_groups_resolve(self):
        record = company("prismhr")
        locations = {w["code"]["raw"] for w in record["work_locations"]}
        groups = {g["code"]["raw"] for g in record["pay_groups"]}
        employees = expected_output("prismhr")["employees"]
        for employee in employees:
            with self.subTest(employee=employee["source"]["employee_id"]):
                self.assertIn(employee["job"]["location"]["raw"], locations)
        runs = [r["pay_group"]["raw"] for r in expected_output("prismhr", "payroll")["pay_runs"] if r["pay_group"]]
        self.assertTrue(runs)
        self.assertLessEqual(set(runs), groups)

    def test_isolved_employee_locations_and_pay_groups_resolve(self):
        record = company("isolved")
        codes = {w["code"]["raw"] for w in record["work_locations"]}
        for employee in expected_output("isolved")["employees"]:
            with self.subTest(employee=employee["source"]["employee_id"]):
                self.assertIn(employee["job"]["location"]["raw"], codes)
        groups = {g["source_id"] for g in record["pay_groups"]}
        runs = {r["pay_group"]["raw"] for r in expected_output("isolved", "payroll")["pay_runs"]}
        self.assertEqual(runs, {"7627"})
        self.assertLessEqual(runs, groups)

    def test_ukg_pay_run_eins_resolve_to_tax_ids(self):
        tax_ids = {t["source_id"] for t in company("ukg-ready")["tax_ids"]}
        runs = {r["pay_group"]["raw"] for r in expected_output("ukg-ready", "payroll")["pay_runs"]}
        self.assertTrue(runs)
        self.assertLessEqual(runs, tax_ids)


if __name__ == "__main__":
    unittest.main()
