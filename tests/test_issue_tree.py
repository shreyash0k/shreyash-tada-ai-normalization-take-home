"""The issue tree behind the web issues page: every issue lands once, under the right node."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from _fixtures import PROVIDERS, expected_output
from normalization.issue_tree import ENTITIES, IssueTreeError, Place, build_provider, expected_text, parse_key

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_web_data  # noqa: E402


def issue(key, code="invalid_date", severity="error"):
    return {"code": code, "severity": severity, "source_path": "person.birthDate", "action": "set null",
            "record_key": key, "raw_value": "2001-02-30", "message": "not a date"}


def outputs(issues=(), employees=(("prismhr:132:F00001", "Finley", "Kowalczyk"),),
            legal_name="Demo Staffing LLP", name="Demo Staffing"):
    data = {entity: {"issues": []} for entity in ENTITIES}
    data["company"]["company"] = {"key": "prismhr:132", "legal_name": legal_name, "name": name}
    data["employee"]["employees"] = [{"key": key, "person": {"first_name": first, "last_name": last}}
                                     for key, first, last in employees]
    data["employee"]["issues"] = list(issues)
    return data


class ParseKey(unittest.TestCase):
    def test_every_key_shape(self):
        cases = [
            ("prismhr", None, Place(None, None, None, None)),
            ("prismhr", "prismhr:132", Place("132", None, "company", None)),
            ("prismhr", "prismhr:132:run:202604", Place("132", None, "run", "202604")),
            ("isolved", "isolved:4046-5806:pg:7627", Place("4046-5806", None, "pg", "7627")),
            ("prismhr", "prismhr:132:F00001", Place("132", "F00001", "employee", None)),
            ("prismhr", "prismhr:132:F00001:dd:0", Place("132", "F00001", "dd", "0")),
            ("prismhr", "prismhr:132:M00006:ded:1", Place("132", "M00006", "ded", "1")),
            ("ukg-ready", "ukg-ready:33704016:12935181567:chk:85940002",
             Place("33704016", "12935181567", "chk", "85940002")),
        ]
        for provider, key, place in cases:
            with self.subTest(key=key):
                self.assertEqual(parse_key(provider, key), place)

    def test_malformed_keys_fail(self):
        for key in ("isolved:4046-5806", "prismhr:132:run", "prismhr::F00001", "prismhr:132:F00001:dd",
                    "prismhr:132:F00001:xx:1", "prismhr:132:run:1:2", "prismhr"):
            with self.subTest(key=key), self.assertRaises(IssueTreeError):
                parse_key("prismhr", key)


class BuildProvider(unittest.TestCase):
    def test_issues_attach_to_their_node(self):
        tree = build_provider("prismhr", "PrismHR", outputs(issues=[
            issue(None, "spec_live_mismatch", "info"),
            issue("prismhr:132", "missing_section", "warning"),
            issue("prismhr:132:run:202604", "inconsistent_allocation", "warning"),
            issue("prismhr:132:F00001"),
            issue("prismhr:132:F00001:dd:0", "masked_value", "info"),
            issue("prismhr:132:X00099", "missing_section", "warning"),
        ]))
        self.assertNotIn("issues", tree)
        [company] = tree["companies"]
        self.assertEqual([(i["record"], i["record_id"]) for i in company["issues"]],
                         [("company", None), ("run", "202604")])
        [employee] = company["employees"]
        self.assertEqual([(i["record"], i["record_id"]) for i in employee["issues"]],
                         [("employee", None), ("dd", "0")])
        self.assertEqual(company["unknown_employees"],
                         [{"key": "prismhr:132:X00099", "id": "X00099", "issues": [
                             {"code": "missing_section", "severity": "warning", "source_path": "person.birthDate",
                              "raw_value": "2001-02-30", "action": "set null", "expected": "not a date",
                              "record": "employee", "record_id": None}]}])

    def test_issue_keeps_only_what_the_page_shows(self):
        tree = build_provider("prismhr", "PrismHR", outputs(issues=[issue("prismhr:132:F00001")]))
        shown = tree["companies"][0]["employees"][0]["issues"][0]
        self.assertEqual(set(shown),
                         {"code", "severity", "source_path", "raw_value", "action", "expected", "record", "record_id"})

    def test_employees_and_clients_are_named(self):
        tree = build_provider("prismhr", "PrismHR", outputs(employees=[
            ("prismhr:132:F00001", "Finley", "Kowalczyk"), ("prismhr:132:M00002", None, None)]))
        [company] = tree["companies"]
        self.assertEqual((company["id"], company["key"], company["name"]), ("132", "prismhr:132", "Demo Staffing LLP"))
        self.assertEqual([(e["id"], e["name"]) for e in company["employees"]],
                         [("F00001", "Finley Kowalczyk"), ("M00002", "M00002")])

    def test_client_name_falls_back_to_plain_name_then_id(self):
        self.assertEqual(build_provider("prismhr", "PrismHR", outputs(legal_name=None))["companies"][0]["name"],
                         "Demo Staffing")
        self.assertEqual(build_provider("prismhr", "PrismHR", outputs(legal_name=None, name=None))
                         ["companies"][0]["name"], "Client 132")

    def test_client_known_only_from_an_issue_is_still_shown(self):
        tree = build_provider("prismhr", "PrismHR", outputs(issues=[issue("prismhr:200:run:1")]))
        self.assertEqual([(c["id"], c["name"]) for c in tree["companies"]],
                         [("132", "Demo Staffing LLP"), ("200", "Client 200")])

    def test_issue_from_another_provider_fails(self):
        with self.assertRaises(IssueTreeError):
            build_provider("prismhr", "PrismHR", outputs(issues=[issue("isolved:4046-5806")]))


class ExpectedText(unittest.TestCase):
    def test_common_constraints(self):
        cases = [
            ("value is not a YYYY-MM-DD date or ISO 8601 date-time", "YYYY-MM-DD"),
            ("citizenship: label is not on the documented allowlist (contracts/isolved/x.json#/a)", "allowlist"),
            ("payFrequency: code has no documented meaning (contracts/isolved/x.json#/a)", "documented code"),
            ("isEmployeeTax must be a boolean (contracts/isolved/x.json#/a)", "boolean"),
            ("usePercent must be a boolean, T or F (contracts/prismhr/x.json#/a)", "boolean, T or F"),
            ("provider returned a masked value", "unmasked value"),
            ("live API returns 'employerId' where the OpenAPI document names 'employerIds' "
             "(contracts/prismhr/x.json#/a)", "employerIds"),
            ("bundle has no responses.pay_items['859205'] entry", "deduction lines"),
            ("bundle has no responses.checks['859205'] entry", "paychecks"),
            (None, None),
        ]
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(expected_text(message), expected)


class GoldenTrees(unittest.TestCase):
    def tree(self, provider):
        return build_provider(provider, provider, {entity: expected_output(provider, entity) for entity in ENTITIES})

    def test_every_keyed_golden_issue_lands_once(self):
        for provider in PROVIDERS:
            tree = self.tree(provider)
            placed = sum(
                len(c["issues"]) + sum(len(e["issues"]) for e in c["employees"] + c["unknown_employees"])
                for c in tree["companies"])
            expected = sum(1 for entity in ENTITIES for i in expected_output(provider, entity)["issues"]
                           if i["record_key"] is not None)
            with self.subTest(provider=provider):
                self.assertEqual(placed, expected)

    def test_employee_counts_match_their_record_keys(self):
        for provider in PROVIDERS:
            golden = [i for entity in ENTITIES for i in expected_output(provider, entity)["issues"]]
            for company in self.tree(provider)["companies"]:
                for employee in company["employees"]:
                    key = employee["key"]
                    owned = [i for i in golden if i["record_key"] and
                             (i["record_key"] == key or i["record_key"].startswith(key + ":"))]
                    with self.subTest(employee=key):
                        self.assertEqual(len(employee["issues"]), len(owned))

    def test_every_golden_employee_has_a_tile(self):
        for provider in PROVIDERS:
            keys = [e["key"] for c in self.tree(provider)["companies"] for e in c["employees"]]
            with self.subTest(provider=provider):
                self.assertEqual(keys, [e["key"] for e in expected_output(provider)["employees"]])


class IssueExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = export_web_data.render_issues()
        cls.data = json.loads(cls.text)

    def test_committed_issue_export_is_current(self):
        self.assertEqual(export_web_data.ISSUES_OUTPUT.read_text(encoding="utf-8"), self.text)

    def test_render_is_deterministic(self):
        self.assertEqual(export_web_data.render_issues(), self.text)

    def test_providers_follow_bundle_order(self):
        self.assertEqual(self.data["export_version"], 1)
        self.assertEqual([p["id"] for p in self.data["providers"]], list(PROVIDERS))
        self.assertEqual([p["name"] for p in self.data["providers"]], ["PrismHR", "isolved", "UKG Ready"])

    def test_check_mode_flags_a_stale_issue_file(self):
        with mock.patch.object(export_web_data, "render_issues", return_value="{}\n"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(export_web_data.main(["--check"]), 1)
        self.assertIn("issues.json", err.getvalue())

    def test_unplaceable_key_fails_the_export(self):
        broken = {**expected_output("prismhr"), "issues": [issue("prismhr:132:F00001:zz:1")]}
        real = export_web_data.load_golden
        with mock.patch.object(export_web_data, "load_golden",
                               side_effect=lambda p, e: broken if (p, e) == ("prismhr", "employee") else real(p, e)):
            with self.assertRaises(export_web_data.ExportError):
                export_web_data.render_issues()


if __name__ == "__main__":
    unittest.main()
