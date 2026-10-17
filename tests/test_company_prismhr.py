"""PrismHR company adapter: golden output plus the injected edge cases."""
import copy
import unittest

from _fixtures import expected_output, fixture_bundle, issues_with, raw_bundle, resolve_code_table, resolve_evidence
from normalization.adapters import prismhr
from normalization.bundle import parse_bundle

COMPANY = "prismhr:132"


def normalize_variant(change):
    raw = copy.deepcopy(raw_bundle("prismhr", "company"))
    change(raw["responses"])
    return prismhr.normalize_company(parse_bundle(raw, entity="company")).to_dict()


def master(responses):
    return responses["get_client_master"]["clientMaster"]


class PrismHRCompanyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle("prismhr", "company")
        cls.output = prismhr.normalize_company(cls.bundle).to_dict()
        cls.company = cls.output["company"]

    def location(self, source_id):
        return next(w for w in self.company["work_locations"] if w["source_id"] == source_id)

    def pay_group(self, source_id):
        return next(g for g in self.company["pay_groups"] if g["source_id"] == source_id)

    def test_matches_golden_output(self):
        self.assertEqual(self.output, expected_output("prismhr", "company"))

    def test_is_deterministic(self):
        self.assertEqual(prismhr.normalize_company(self.bundle).to_dict(), self.output)

    def test_profile_fields(self):
        company = self.company
        self.assertEqual(company["key"], COMPANY)
        self.assertEqual((company["name"], company["legal_name"]),
                         ("Dunder Mifflin", "Dunder Mifflin Paper Company, Inc."))
        self.assertEqual(company["status"], {"raw": "A", "label": "Active", "value": "active"})
        self.assertEqual(company["status_date"], "2019-04-01")
        self.assertEqual(company["entity_type"], {"raw": "M", "label": "Limited Liability Partnership", "value": None})
        self.assertEqual(company["service_type"]["label"], "Professional Employer Services")
        self.assertEqual((company["naics_code"], company["sic_code"]), ("561320", "7363"))
        self.assertEqual(company["address"]["kind"], "mailing")
        self.assertTrue(company["address"]["postal_code"].endswith("-1234"))
        self.assertEqual((company["phone"]["kind"], company["phone"]["extension"]), ("work", "101"))
        self.assertEqual(company["email"], {"kind": "work", "address": "payroll@dundermifflin.example"})
        self.assertEqual(company["website"], "https://dundermifflin.example")
        self.assertEqual(company["unmapped"]["clientMaster.businessDescription"], "Paper and office supplies")

    def test_unmasked_federal_id_becomes_the_ein_and_one_tax_id(self):
        self.assertEqual(self.company["ein"], "99-0000132")
        self.assertEqual([(t["key"], t["tax_id"]) for t in self.company["tax_ids"]],
                         [(f"{COMPANY}:ein:99-0000132", "99-0000132")])

    def test_masked_federal_id_leaves_ein_null(self):
        output = normalize_variant(lambda r: master(r).update(federalIdNumber="**********"))
        self.assertIsNone(output["company"]["ein"])
        self.assertEqual(output["company"]["tax_ids"], [])
        found = issues_with(output, "masked_value")
        self.assertEqual([(i["source_path"], i["severity"]) for i in found],
                         [("clientMaster.federalIdNumber", "warning")])

    def test_each_status_class(self):
        expected = {"A": "active", "P": "pending", "I": "inactive", "C": "terminating", "T": "terminated",
                    "Z": "unknown"}
        for raw, value in expected.items():
            with self.subTest(raw=raw):
                output = normalize_variant(lambda r: master(r).update(statusClass=raw))
                self.assertEqual(output["company"]["status"]["value"], value)
                self.assertEqual(len(issues_with(output, "undocumented_code", "statusClass")), int(raw == "Z"))

    def test_unlisted_corporation_type_keeps_the_raw_code(self):
        output = normalize_variant(lambda r: master(r).update(corporationType="X"))
        self.assertEqual(output["company"]["entity_type"], {"raw": "X", "label": None, "value": None})
        self.assertEqual(len(issues_with(output, "undocumented_code", "corporationType")), 1)

    def test_live_only_fields_are_reported_once(self):
        found = issues_with(self.output, "spec_live_mismatch", "clientMaster")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["raw_value"], list(prismhr.LIVE_ONLY_CLIENT_FIELDS))
        self.assertIs(self.company["unmapped"]["clientMaster.eVerify"], True)

    def test_locations(self):
        self.assertEqual([w["source_id"] for w in self.company["work_locations"]], ["1", "2", "3", "OLD", "REM"])
        site = self.location("1")
        self.assertEqual(site["key"], f"{COMPANY}:loc:1")
        self.assertEqual(site["code"], {"raw": "1", "label": "Site 1", "value": None})
        self.assertEqual(site["address"]["kind"], "work")
        self.assertEqual((site["active"], site["end_date"], site["remote"]), (True, None, False))
        old = self.location("OLD")
        self.assertEqual((old["active"], old["end_date"]), (False, "2024-06-30"))
        self.assertIs(self.location("REM")["remote"], True)

    def test_pay_groups_take_frequency_from_the_schedule(self):
        self.assertEqual([g["source_id"] for g in self.company["pay_groups"]], ["WFRI", "M", "SEMI"])
        weekly = self.pay_group("WFRI")
        self.assertEqual(weekly["code"], {"raw": "WFRI", "label": "Weekly Paid Friday", "value": None})
        self.assertEqual(weekly["frequency"], {"raw": "W", "label": "Weekly (PayDay {MON-SUN})", "value": "weekly"})
        self.assertEqual(self.pay_group("M")["frequency"]["value"], "monthly")
        self.assertIn("clientPayrollSchedule[1].payDay", weekly["unmapped"])
        self.assertNotIn("clientPayrollSchedule[1].groupId", weekly["unmapped"])
        semi = self.pay_group("SEMI")
        self.assertIsNone(semi["frequency"])
        self.assertEqual(semi["unmapped"], {})

    def test_singular_schedule_key_is_reported(self):
        found = issues_with(self.output, "spec_live_mismatch", "clientPayrollSchedule")
        self.assertEqual([(i["source_path"], i["severity"]) for i in found], [("clientPayrollSchedule", "info")])

    def test_plural_schedule_key_reads_without_an_issue(self):
        def plural(responses):
            schedule = responses["get_payroll_schedule"]
            schedule["clientPayrollSchedules"] = schedule.pop("clientPayrollSchedule")
        output = normalize_variant(plural)
        self.assertEqual(issues_with(output, "spec_live_mismatch", "clientPayrollSchedule"), [])
        groups = {g["source_id"]: g["frequency"] for g in output["company"]["pay_groups"]}
        self.assertEqual(groups["WFRI"]["value"], "weekly")

    def test_unlisted_schedule_period_is_reported_once(self):
        def unlisted(responses):
            for row in responses["get_payroll_schedule"]["clientPayrollSchedule"]:
                row["payPeriod"] = "Q"
        output = normalize_variant(unlisted)
        found = issues_with(output, "undocumented_code", "payPeriod")
        self.assertEqual([i["raw_value"] for i in found], ["Q"])

    def test_missing_client_codes_leaves_lists_empty(self):
        output = normalize_variant(lambda r: r.pop("get_client_codes"))
        self.assertEqual((output["company"]["work_locations"], output["company"]["pay_groups"]), ([], []))
        found = issues_with(output, "missing_section")
        self.assertEqual([(i["source_path"], i["severity"]) for i in found],
                         [("responses.get_client_codes", "info")])

    def test_missing_schedule_leaves_frequency_null(self):
        output = normalize_variant(lambda r: r.pop("get_payroll_schedule"))
        self.assertEqual([g["frequency"] for g in output["company"]["pay_groups"]], [None, None, None])

    def test_code_tables_quote_the_spec_descriptions(self):
        status = resolve_code_table(prismhr.CLIENT_STATUS)
        self.assertEqual(sorted(prismhr.CLIENT_STATUS.entries), sorted(prismhr.CLIENT_STATUS_LABELS))
        for code, label in prismhr.CLIENT_STATUS_LABELS.items():
            with self.subTest(code=code):
                self.assertIn(f"“{code}” ({label})", status)
        for name, labels in (("corporationType", prismhr.CORPORATION_TYPE_LABELS),
                             ("serviceType", prismhr.SERVICE_TYPE_LABELS)):
            text = resolve_evidence(f"{prismhr.CLIENT}/{name}/description")
            for code, label in labels.items():
                with self.subTest(field=name, code=code):
                    self.assertIn(f"'{code}' ({label})", text)
        periods = resolve_code_table(prismhr.SCHEDULE_PAY_PERIOD)
        for code in prismhr.SCHEDULE_PAY_PERIOD.entries:
            with self.subTest(code=code):
                self.assertIn(f"'{code}' (", periods)


if __name__ == "__main__":
    unittest.main()
