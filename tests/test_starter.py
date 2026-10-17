"""Starter plumbing checks only. These do not assess transformation correctness."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from normalization.__main__ import main
from normalization.adapters import ADAPTERS, ENTITIES
from normalization.references import all_readiness_issues, load_reference, readiness_issues


class StarterChecks(unittest.TestCase):
    def test_expected_providers_and_entities_are_exposed(self):
        self.assertEqual(set(ADAPTERS), {"prismhr", "isolved", "ukg-ready"})
        self.assertEqual(set(ENTITIES), {"company", "employee", "direct-deposit", "deduction", "payroll"})

    def test_reference_readiness_matches_distributed_materials(self):
        self.assertEqual(all_readiness_issues(), {"prismhr": [], "isolved": [], "ukg-ready": []})
        self.assertEqual(load_reference("prismhr")["lookup_status"], "verified")
        for provider in ("isolved", "ukg-ready"):
            with self.subTest(provider=provider):
                ref = load_reference(provider)
                self.assertEqual(ref["lookup_status"], "verified")
                self.assertTrue(ref["lookups"])
                self.assertEqual(ref["distribution"]["status"], "user_approved_private_upload")
                self.assertFalse(ref["distribution"]["provider_redistribution_permission_verified"])

    def test_readiness_command_exits_zero_for_supplied_packs(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check-inputs"]), 0)

    def test_normalize_command_writes_direct_deposits(self):
        bundle = Path(__file__).resolve().parent / "fixtures" / "ukg-ready" / "direct-deposit-bundle.json"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["normalize", "--provider", "ukg-ready", "--entity", "direct-deposit",
                             "--input", str(bundle), "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue().strip(), "9 direct deposits, 2 issues")
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))["direct_deposits"]), 9)

    def test_normalize_command_writes_deductions(self):
        bundle = Path(__file__).resolve().parent / "fixtures" / "prismhr" / "deduction-bundle.json"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["normalize", "--provider", "prismhr", "--entity", "deduction",
                             "--input", str(bundle), "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue().strip(), "13 deductions, 2 issues")
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))["deductions"]), 13)

    def test_normalize_command_writes_payroll(self):
        bundle = Path(__file__).resolve().parent / "fixtures" / "ukg-ready" / "payroll-bundle.json"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["normalize", "--provider", "ukg-ready", "--entity", "payroll",
                             "--input", str(bundle), "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue().strip(), "1 pay runs, 8 paychecks, 5 issues")
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual((len(written["pay_runs"]), len(written["paychecks"])), (1, 8))

    def test_normalize_command_writes_company(self):
        bundle = Path(__file__).resolve().parent / "fixtures" / "prismhr" / "company-bundle.json"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["normalize", "--provider", "prismhr", "--entity", "company",
                             "--input", str(bundle), "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue().strip(),
                             "1 company, 5 work locations, 3 pay groups, 1 tax ids, 2 issues")
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(written["company"]["key"], "prismhr:132")

    def test_normalize_command_rejects_a_bundle_missing_the_entity_responses(self):
        bundle = Path(__file__).resolve().parent / "fixtures" / "prismhr" / "employee-bundle.json"
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            code = main(["normalize", "--provider", "prismhr", "--entity", "direct-deposit",
                         "--input", str(bundle), "--output", str(Path(tmp) / "out.json")])
        self.assertEqual(code, 1)


class ReadinessIssueChecks(unittest.TestCase):
    """Negative paths for readiness_issues, run against a synthetic contract root."""

    PROVIDER = "demo"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.provider_dir = self.root / "contracts" / self.PROVIDER
        self.provider_dir.mkdir(parents=True)

    def write_pack(self, **overrides):
        pack = {
            "provider": self.PROVIDER,
            "reference_version": "test-1",
            "lookup_status": "verified",
            "lookups": [],
            "distribution": {
                "status": "user_approved_private_upload",
                "evidence_reference": "../../docs/REFERENCE_AUDIT.md#private-upload-authorization",
            },
            "openapi": {"status": "not_available", "relative_path": None, "version": None, "sha256": None},
            "reference_artifact": {"relative_path": "reference-schemas.json", "sha256": "abc123"},
        }
        pack.update(overrides)
        (self.provider_dir / "lookup-reference.json").write_text(json.dumps(pack), encoding="utf-8")
        return pack

    def write_artifact(self, name="reference-schemas.json"):
        (self.provider_dir / name).write_text("{}", encoding="utf-8")

    def issues(self):
        return readiness_issues(self.PROVIDER, self.root)

    def test_missing_pack_reports_single_read_error(self):
        issues = self.issues()
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].startswith("Cannot read reference metadata: "))

    def test_well_formed_not_available_pack_has_no_issues(self):
        self.write_pack()
        self.write_artifact()
        self.assertEqual(self.issues(), [])

    def test_unrecognized_distribution_status_is_reported(self):
        self.write_pack(distribution={"status": "pending", "evidence_reference": "x#y"})
        self.write_artifact()
        self.assertEqual(self.issues(), ["Candidate-distribution permission has not been verified."])

    def test_distribution_without_evidence_is_reported(self):
        self.write_pack(distribution={"status": "user_approved_private_upload"})
        self.write_artifact()
        self.assertEqual(self.issues(), ["Candidate-distribution permission has not been verified."])

    def test_not_available_without_reference_artifact_reports_missing_filename(self):
        pack = self.write_pack()
        del pack["reference_artifact"]
        (self.provider_dir / "lookup-reference.json").write_text(json.dumps(pack), encoding="utf-8")
        self.assertIn("Reference artifact filename is missing.", self.issues())

    def test_reference_artifact_pointing_at_missing_file_is_reported(self):
        self.write_pack()
        self.assertEqual(self.issues(),
                         ["Reference artifact file must exist inside the provider contract directory."])

    def test_reference_artifact_escaping_provider_directory_is_reported(self):
        self.write_pack(reference_artifact={"relative_path": "../escape.json", "sha256": "abc123"})
        (self.root / "contracts" / "escape.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.issues(),
                         ["Reference artifact file must exist inside the provider contract directory."])

    def test_reference_artifact_without_checksum_is_reported(self):
        self.write_pack(reference_artifact={"relative_path": "reference-schemas.json"})
        self.write_artifact()
        self.assertEqual(self.issues(), ["Reference artifact checksum is missing."])

    def test_other_openapi_status_is_still_reported(self):
        self.write_pack(openapi={"status": "pending", "relative_path": None, "version": None, "sha256": None})
        self.write_artifact()
        self.assertIn("OpenAPI artifact is absent or unverified.", self.issues())


if __name__ == "__main__":
    unittest.main()
