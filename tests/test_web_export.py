"""The web app's coverage file: current, complete, and consistent with the golden outputs."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from _fixtures import expected_output
from normalization.bundle import PROVIDER_SPECS
from normalization.field_map import FIELD_MAP, canonical_fields, is_filled

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_web_data  # noqa: E402

PROVIDERS = tuple(PROVIDER_SPECS)


class WebExportChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = export_web_data.render()
        cls.data = json.loads(cls.text)
        cls.by_id = {provider["id"]: provider for provider in cls.data["providers"]}

    def test_committed_export_is_current(self):
        self.assertEqual(export_web_data.OUTPUT.read_text(encoding="utf-8"), self.text)

    def test_check_mode_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(export_web_data.main(["--check"]), 0)

    def test_render_is_deterministic(self):
        self.assertEqual(export_web_data.render(), self.text)

    def test_providers_follow_bundle_order(self):
        self.assertEqual([provider["id"] for provider in self.data["providers"]], list(PROVIDERS))

    def test_rows_follow_the_field_map(self):
        for provider in PROVIDERS:
            rows = self.by_id[provider]["coverage"]
            with self.subTest(provider=provider):
                self.assertEqual([row["field"] for row in rows], list(canonical_fields()))
                for row in rows:
                    entry = FIELD_MAP[provider][row["field"]]
                    self.assertEqual((row["status"], row["source"], row["evidence"]),
                                     (entry.status, entry.source, entry.evidence))

    def test_counts_agree_with_golden_output(self):
        for provider in PROVIDERS:
            employees = expected_output(provider)["employees"]
            data = self.by_id[provider]
            with self.subTest(provider=provider):
                self.assertEqual(data["summary"]["employees"], len(employees))
                self.assertEqual(data["summary"]["fields_total"], len(canonical_fields()))
                for row in data["coverage"]:
                    self.assertEqual(row["total"], len(employees))
                    self.assertEqual(row["filled"], sum(is_filled(e, row["field"]) for e in employees))

    def test_export_holds_no_provider_values(self):
        for provider in PROVIDERS:
            for employee in expected_output(provider)["employees"]:
                last_name = employee["person"]["last_name"]
                if last_name:
                    with self.subTest(provider=provider, employee=employee["key"]):
                        self.assertNotIn(last_name, self.text)

    def test_missing_field_map_entry_fails_the_export(self):
        with mock.patch.dict(FIELD_MAP["prismhr"]):
            del FIELD_MAP["prismhr"]["person.first_name"]
            with self.assertRaises(export_web_data.ExportError):
                export_web_data.render()


if __name__ == "__main__":
    unittest.main()
