"""One linked document per company: the five data types merged and their links checked."""
import contextlib
import dataclasses
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _fixtures import ENTITIES, FIXTURES, PROVIDERS, expected_output, schema
from normalization.__main__ import main
from normalization.adapters import ADAPTERS
from normalization.canonical import Issue, IssueCode, Severity
from normalization.canonical.schema_check import validate
from normalization.company_document import build_document, link_issues, load_company_bundles

LISTS = ("employees", "direct_deposits", "deductions", "pay_runs", "paychecks")


def merged_golden(provider: str) -> dict:
    outputs = [expected_output(provider, entity) for entity in ENTITIES]
    issues, seen = [], set()
    for output in outputs:
        for issue in output["issues"]:
            marker = json.dumps(issue, sort_keys=True)
            if marker not in seen:
                seen.add(marker)
                issues.append(issue)
    merged = {"provider": provider, "company": outputs[0]["company"]}
    for name in LISTS:
        merged[name] = [record for output in outputs for record in output[name]]
    merged["issues"] = issues
    merged["schema_version"] = outputs[0]["schema_version"]
    return merged


class CompanyDocumentChecks(unittest.TestCase):
    def document(self, provider):
        return build_document(load_company_bundles(FIXTURES / provider))

    def test_document_merges_the_five_golden_outputs(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(self.document(provider).to_dict(), merged_golden(provider))

    def test_document_matches_the_schema(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(validate(self.document(provider).to_dict(), schema()), [])

    def test_identical_issues_are_kept_once(self):
        shared = Issue(IssueCode.SPEC_LIVE_MISMATCH, Severity.WARNING, "responses", "read the live shape")
        real = ADAPTERS["prismhr"]

        class Repeating:
            def normalize(self, entity, bundle, reference):
                output = real.normalize(entity, bundle, reference)
                return dataclasses.replace(output, issues=[*output.issues, shared])

        with mock.patch.dict(ADAPTERS, {"prismhr": Repeating()}):
            issues = self.document("prismhr").issues
        self.assertEqual(issues.count(shared), 1)

    def test_fixture_links_all_resolve(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(link_issues(self.document(provider)), [])

    def test_broken_links_are_reported_and_records_kept(self):
        document = self.document("prismhr")
        deduction = dataclasses.replace(document.deductions[0], employee_key="prismhr:132:NOBODY")
        paycheck = dataclasses.replace(document.paychecks[0], pay_run_key="prismhr:132:run:MISSING")
        deposit = dataclasses.replace(document.direct_deposits[0], company_key="prismhr:999")
        broken = dataclasses.replace(document, deductions=[deduction, *document.deductions[1:]],
                                     paychecks=[paycheck, *document.paychecks[1:]],
                                     direct_deposits=[deposit, *document.direct_deposits[1:]])
        found = [issue.to_dict() for issue in link_issues(broken)]
        self.assertEqual([(i["code"], i["severity"], i["source_path"], i["record_key"], i["raw_value"])
                          for i in found],
                         [("broken_link", "warning", "company_key", deposit.key, "prismhr:999"),
                          ("broken_link", "warning", "employee_key", deduction.key, "prismhr:132:NOBODY"),
                          ("broken_link", "warning", "pay_run_key", paycheck.key, "prismhr:132:run:MISSING")])
        self.assertEqual(len(broken.deductions), len(document.deductions))

    def test_unset_pay_run_key_is_not_a_broken_link(self):
        document = self.document("prismhr")
        paycheck = dataclasses.replace(document.paychecks[0], pay_run_key=None)
        self.assertEqual(link_issues(dataclasses.replace(document, paychecks=[paycheck])), [])


class CompanyBundleLoading(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "prismhr"
        shutil.copytree(FIXTURES / "prismhr", self.folder)

    def rewrite(self, name, change):
        path = self.folder / name
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_missing_bundle_file_is_named(self):
        (self.folder / "payroll-bundle.json").unlink()
        with self.assertRaisesRegex(ValueError, "payroll-bundle.json"):
            load_company_bundles(self.folder)

    def test_bundles_from_another_provider_are_rejected(self):
        shutil.copy(FIXTURES / "ukg-ready" / "payroll-bundle.json", self.folder / "payroll-bundle.json")
        with self.assertRaisesRegex(ValueError, "provider"):
            load_company_bundles(self.folder)

    def test_bundles_for_another_company_are_rejected(self):
        self.rewrite("deduction-bundle.json", lambda data: data["request"].update(client_id="999"))
        with self.assertRaisesRegex(ValueError, "company"):
            load_company_bundles(self.folder)

    def test_command_writes_the_document_and_summary(self):
        output = Path(self._tmp.name) / "doc.json"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["normalize-company", "--input", str(self.folder), "--output", str(output)])
        self.assertEqual(code, 0)
        expected = merged_golden("prismhr")
        counts = {name: len(expected[name]) for name in LISTS}
        self.assertEqual(stderr.getvalue().strip(),
                         f"1 company, {counts['employees']} employees, {counts['direct_deposits']} direct deposits, "
                         f"{counts['deductions']} deductions, {counts['pay_runs']} pay runs, "
                         f"{counts['paychecks']} paychecks, 0 broken links, {len(expected['issues'])} issues")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), expected)

    def test_command_refuses_to_overwrite_and_reports_bad_input(self):
        output = Path(self._tmp.name) / "doc.json"
        output.write_text("{}", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["normalize-company", "--input", str(self.folder), "--output", str(output)]), 1)
            (self.folder / "employee-bundle.json").unlink()
            self.assertEqual(main(["normalize-company", "--input", str(self.folder),
                                   "--output", str(Path(self._tmp.name) / "other.json")]), 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "{}")


if __name__ == "__main__":
    unittest.main()
