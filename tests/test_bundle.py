"""Capture bundle envelope validation."""
import copy
import unittest
from datetime import date

from _fixtures import fixture_bundle, raw_bundle
from normalization.bundle import PROVIDER_SPECS, parse_bundle


class BundleEnvelopeChecks(unittest.TestCase):
    def test_fixture_bundles_parse(self):
        for provider in PROVIDER_SPECS:
            with self.subTest(provider=provider):
                bundle = fixture_bundle(provider)
                self.assertEqual(bundle.provider, provider)
                self.assertEqual(bundle.captured_at, date(2026, 10, 15))
                for key in PROVIDER_SPECS[provider].request_keys:
                    self.assertTrue(bundle.request[key])

    def assertRejected(self, data, fragment):
        with self.assertRaises(ValueError) as caught:
            parse_bundle(data)
        self.assertIn(fragment, str(caught.exception))

    def test_missing_envelope_keys_are_reported(self):
        data = raw_bundle("prismhr")
        del data["captured_at"]
        self.assertRejected(data, "captured_at")

    def test_unknown_provider_and_bad_version(self):
        data = raw_bundle("prismhr")
        self.assertRejected(dict(data, provider="workday"), "unknown provider")
        self.assertRejected(dict(data, bundle_version=2), "bundle_version")

    def test_captured_at_must_be_a_date(self):
        self.assertRejected(dict(raw_bundle("isolved"), captured_at="2026-13-01"), "captured_at")

    def test_request_keys_per_provider(self):
        data = raw_bundle("isolved")
        del data["request"]["legal_id"]
        self.assertRejected(data, "request.legal_id")

    def test_required_response_keys_and_container_types(self):
        data = raw_bundle("ukg-ready")
        del data["responses"]["pay_info"]
        self.assertRejected(data, "responses.pay_info")
        data = raw_bundle("prismhr")
        data["responses"]["get_employee"] = {}
        self.assertRejected(data, "responses.get_employee must be a JSON list")

    def test_unknown_response_keys_are_rejected(self):
        data = raw_bundle("prismhr")
        data["responses"]["direct_deposits"] = []
        self.assertRejected(data, "unknown keys")

    def test_optional_keys_may_be_absent(self):
        data = copy.deepcopy(raw_bundle("isolved"))
        for key in ("employee_detail", "personal", "name_address"):
            del data["responses"][key]
        self.assertEqual(parse_bundle(data).provider, "isolved")


if __name__ == "__main__":
    unittest.main()
