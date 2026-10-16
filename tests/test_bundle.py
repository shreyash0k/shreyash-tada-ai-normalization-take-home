"""Capture bundle envelope validation."""
import copy
import unittest
from datetime import date

from _fixtures import ENTITIES, fixture_bundle, raw_bundle
from normalization.bundle import BUNDLE_ENTITIES, PROVIDER_SPECS, parse_bundle


class BundleEnvelopeChecks(unittest.TestCase):
    def test_fixture_bundles_parse(self):
        for provider in PROVIDER_SPECS:
            for entity in ENTITIES:
                with self.subTest(provider=provider, entity=entity):
                    bundle = fixture_bundle(provider, entity)
                    self.assertEqual(bundle.provider, provider)
                    self.assertEqual(bundle.captured_at, date(2026, 10, 15))
                    for key in PROVIDER_SPECS[provider].request_keys:
                        self.assertTrue(bundle.request[key])

    def test_every_provider_lists_every_bundle_entity(self):
        for provider, spec in PROVIDER_SPECS.items():
            with self.subTest(provider=provider):
                self.assertEqual(set(spec.required), set(BUNDLE_ENTITIES))
                self.assertEqual(set(spec.optional), set(BUNDLE_ENTITIES))

    def assertRejected(self, data, fragment, entity="employee"):
        with self.assertRaises(ValueError) as caught:
            parse_bundle(data, entity=entity)
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

    def test_required_keys_depend_on_the_entity(self):
        employee_bundle = raw_bundle("ukg-ready")
        self.assertRejected(employee_bundle, "responses.direct_deposits is required", entity="direct-deposit")
        deposit_bundle = raw_bundle("prismhr", "direct-deposit")
        self.assertRejected(deposit_bundle, "responses.get_employee is required", entity="employee")
        data = raw_bundle("isolved", "direct-deposit")
        data["responses"]["direct_deposits"] = []
        self.assertRejected(data, "responses.direct_deposits must be a JSON dict", entity="direct-deposit")

    def test_deduction_keys_per_provider(self):
        self.assertRejected(raw_bundle("prismhr"), "responses.get_deductions is required", entity="deduction")
        self.assertRejected(raw_bundle("isolved"), "responses.pay_items is required", entity="deduction")
        data = raw_bundle("ukg-ready", "deduction")
        del data["responses"]["deduction_detail"]
        self.assertRejected(data, "responses.deduction_detail is required", entity="deduction")
        data = raw_bundle("ukg-ready", "deduction")
        data["responses"]["deductions"] = []
        self.assertRejected(data, "responses.deductions must be a JSON dict", entity="deduction")

    def test_one_bundle_can_feed_every_entity(self):
        data = raw_bundle("isolved")
        data["responses"]["direct_deposits"] = raw_bundle("isolved", "direct-deposit")["responses"]["direct_deposits"]
        data["responses"]["pay_items"] = raw_bundle("isolved", "deduction")["responses"]["pay_items"]
        for entity in ENTITIES:
            with self.subTest(entity=entity):
                self.assertEqual(parse_bundle(data, entity=entity).provider, "isolved")

    def test_entities_without_bundles_are_refused(self):
        with self.assertRaises(ValueError):
            parse_bundle(raw_bundle("prismhr"), entity="payroll")

    def test_optional_keys_may_be_absent(self):
        data = copy.deepcopy(raw_bundle("isolved"))
        for key in ("employee_detail", "personal", "name_address"):
            del data["responses"][key]
        self.assertEqual(parse_bundle(data).provider, "isolved")


if __name__ == "__main__":
    unittest.main()
