"""The web app's coverage file: current, complete, and consistent with the field maps."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from _fixtures import expected_output
from normalization import company_field_map, deduction_field_map, deposit_field_map, field_map, payroll_field_map
from normalization.bundle import PROVIDER_SPECS
from normalization.field_map import MAPPED, NOT_OFFERED

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_web_data  # noqa: E402

PROVIDERS = tuple(PROVIDER_SPECS)
ENTITY_MAPS = {"employee": field_map, "direct-deposit": deposit_field_map, "deduction": deduction_field_map,
               "payroll": payroll_field_map, "company": company_field_map}


class WebExportChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = export_web_data.render()
        cls.data = json.loads(cls.text)
        cls.by_id = {entity: {provider["id"]: provider for provider in providers}
                     for entity, providers in cls.data["entities"].items()}

    def test_committed_export_is_current(self):
        self.assertEqual(export_web_data.OUTPUT.read_text(encoding="utf-8"), self.text)

    def test_check_mode_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(export_web_data.main(["--check"]), 0)

    def test_render_is_deterministic(self):
        self.assertEqual(export_web_data.render(), self.text)

    def test_export_holds_every_data_type(self):
        self.assertEqual(self.data["export_version"], 2)
        self.assertEqual(list(self.data["entities"]), list(ENTITY_MAPS))

    def test_providers_follow_bundle_order(self):
        for entity, providers in self.data["entities"].items():
            with self.subTest(entity=entity):
                self.assertEqual([provider["id"] for provider in providers], list(PROVIDERS))

    def test_rows_follow_the_field_map(self):
        for entity, module in ENTITY_MAPS.items():
            for provider in PROVIDERS:
                rows = self.by_id[entity][provider]["coverage"]
                with self.subTest(entity=entity, provider=provider):
                    self.assertEqual([row["field"] for row in rows], list(module.canonical_fields()))
                    for row in rows:
                        entry = module.FIELD_MAP[provider][row["field"]]
                        self.assertEqual(set(row), {"field", "section", "status", "source", "evidence", "reason"})
                        self.assertEqual(row["section"], module.section(row["field"]))
                        self.assertEqual((row["status"], row["source"], row["evidence"], row["reason"]),
                                         (entry.status, entry.source, entry.evidence, entry.reason))

    def test_summary_counts_follow_field_map(self):
        for entity, module in ENTITY_MAPS.items():
            for provider in PROVIDERS:
                entries = module.FIELD_MAP[provider]
                summary = self.by_id[entity][provider]["summary"]
                with self.subTest(entity=entity, provider=provider):
                    self.assertEqual(set(summary), {"fields_total", "fields_offered", "fields_mapped"})
                    self.assertEqual(summary["fields_total"], len(module.canonical_fields()))
                    self.assertEqual(summary["fields_offered"],
                                     sum(entry.status != NOT_OFFERED for entry in entries.values()))
                    self.assertEqual(summary["fields_mapped"],
                                     sum(entry.status == MAPPED for entry in entries.values()))

    def test_export_holds_no_provider_values(self):
        for provider in PROVIDERS:
            for employee in expected_output(provider)["employees"]:
                last_name = employee["person"]["last_name"]
                if last_name:
                    with self.subTest(provider=provider, employee=employee["key"]):
                        self.assertNotIn(last_name, self.text)
            for deposit in expected_output(provider, "direct-deposit")["direct_deposits"]:
                for value in (deposit["bank_name"], deposit["routing_number"]):
                    if value:
                        with self.subTest(provider=provider, deposit=deposit["key"]):
                            self.assertNotIn(value, self.text)
            for deduction in expected_output(provider, "deduction")["deductions"]:
                for value in ((deduction["payee"] or {}).get("name"), (deduction["code"] or {}).get("label")):
                    if value:
                        with self.subTest(provider=provider, deduction=deduction["key"]):
                            self.assertNotIn(value, self.text)
            payroll = expected_output(provider, "payroll")
            for run in payroll["pay_runs"]:
                if run["description"]:
                    with self.subTest(provider=provider, run=run["key"]):
                        self.assertNotIn(run["description"], self.text)
            for paycheck in payroll["paychecks"]:
                for earning in paycheck["earnings"]:
                    label = (earning["code"] or {}).get("label")
                    if label:
                        with self.subTest(provider=provider, paycheck=paycheck["key"], label=label):
                            self.assertNotIn(label, self.text)
            company = expected_output(provider, "company")["company"]
            for value in (company["name"], company["legal_name"], (company["address"] or {}).get("line1")):
                if value:
                    with self.subTest(provider=provider, value=value):
                        self.assertNotIn(value, self.text)
            for location in company["work_locations"]:
                label = (location["code"] or {}).get("label")
                if label:
                    with self.subTest(provider=provider, location=location["key"], label=label):
                        self.assertNotIn(label, self.text)
            for group in company["pay_groups"]:
                label = (group["code"] or {}).get("label")
                if label:
                    with self.subTest(provider=provider, group=group["key"], label=label):
                        self.assertNotIn(label, self.text)

    def test_missing_field_map_entry_fails_the_export(self):
        for module, field in ((field_map, "person.first_name"), (deposit_field_map, "bank_name"),
                              (deduction_field_map, "code"), (payroll_field_map, "pay_run.type"),
                              (company_field_map, "company.name")):
            with self.subTest(field=field), mock.patch.dict(module.FIELD_MAP["prismhr"]):
                del module.FIELD_MAP["prismhr"][field]
                with self.assertRaises(export_web_data.ExportError):
                    export_web_data.render()


if __name__ == "__main__":
    unittest.main()
