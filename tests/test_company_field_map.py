"""The company coverage map: complete, evidenced, and consistent with the golden outputs."""
import unittest

from _fixtures import expected_output, resolve_evidence, schema
from normalization.bundle import PROVIDER_SPECS
from normalization.company_field_map import (
    FIELD_MAP,
    SECTION_FIELDS,
    canonical_fields,
    is_filled,
    section,
)
from normalization.field_map import MAPPED, NOT_MAPPED_YET, NOT_OFFERED, STATUSES

PROVIDERS = tuple(PROVIDER_SPECS)
SKIP_COMPANY = {"key", "source", "unmapped", "tax_ids", "work_locations", "pay_groups"}
CONTACT = {"address", "phone", "email", "website"}
LIST_DEFS = {"tax_ids": "TaxId", "work_locations": "WorkLocation", "pay_groups": "PayGroup"}
SKIP_LIST = {"key", "source_id", "unmapped"}


def golden_company(provider: str) -> dict:
    return expected_output(provider, "company")


class CompanyFieldMapChecks(unittest.TestCase):
    def test_every_provider_has_an_entry_for_every_row(self):
        rows = set(canonical_fields())
        self.assertEqual(len(canonical_fields()), 27)
        self.assertEqual(set(FIELD_MAP), set(PROVIDERS))
        for provider, entries in FIELD_MAP.items():
            with self.subTest(provider=provider):
                self.assertEqual(set(entries), rows)

    def test_rows_cover_every_value_field_of_the_schema(self):
        defs = schema()["$defs"]
        expected = set()
        for field in defs["Company"]["properties"]:
            if field in SKIP_COMPANY:
                continue
            prefix = "contact" if field in CONTACT else "company"
            expected.add(f"{prefix}.{field}")
        for name, defn in LIST_DEFS.items():
            for field in defs[defn]["properties"]:
                if field in SKIP_LIST:
                    continue
                if field == "effective":
                    expected.update(f"{name}.effective.{child}" for child in defs["DateRange"]["properties"])
                else:
                    expected.add(f"{name}.{field}")
        self.assertEqual(set(canonical_fields()), expected)

    def test_each_row_belongs_to_one_section(self):
        for name, fields in SECTION_FIELDS.items():
            for field in fields:
                with self.subTest(field=field):
                    self.assertEqual(section(field), name)

    def test_entries_carry_the_details_their_status_needs(self):
        for provider, entries in FIELD_MAP.items():
            for field, entry in entries.items():
                with self.subTest(provider=provider, field=field):
                    self.assertIn(entry.status, STATUSES)
                    self.assertIn(".json#/", entry.evidence)
                    if entry.status == NOT_OFFERED:
                        self.assertIsNone(entry.source)
                        self.assertTrue(entry.reason)
                    else:
                        self.assertTrue(entry.source)
                    if entry.status == NOT_MAPPED_YET:
                        self.assertTrue(entry.reason)
                    if entry.status != MAPPED:
                        self.assertIsNone(entry.sample_gap)

    def test_evidence_pointers_resolve(self):
        for provider, entries in FIELD_MAP.items():
            for field, entry in entries.items():
                with self.subTest(provider=provider, field=field):
                    try:
                        resolve_evidence(entry.evidence)
                    except (KeyError, IndexError, ValueError, OSError) as exc:
                        self.fail(f"{entry.evidence} does not resolve: {exc!r}")

    def test_unmapped_rows_are_empty_in_golden_output(self):
        for provider, entries in FIELD_MAP.items():
            company = golden_company(provider)
            for field, entry in entries.items():
                if entry.status == MAPPED:
                    continue
                with self.subTest(provider=provider, field=field, status=entry.status):
                    self.assertFalse(is_filled(company, field))

    def test_mapped_rows_are_filled_or_explain_the_gap(self):
        for provider, entries in FIELD_MAP.items():
            company = golden_company(provider)
            for field, entry in entries.items():
                if entry.status != MAPPED:
                    continue
                with self.subTest(provider=provider, field=field):
                    filled = is_filled(company, field)
                    if entry.sample_gap:
                        self.assertFalse(filled, "sample_gap is set but the sample fills the field")
                    else:
                        self.assertTrue(filled, "mapped field is never filled; add sample_gap")

    def test_is_filled_reads_the_profile_and_the_lists(self):
        output = {
            "company": {
                "name": "Acme",
                "ein": None,
                "address": {"line1": "1 Main"},
                "phone": None,
                "tax_ids": [{"tax_id": "99", "name": None}],
                "work_locations": [],
                "pay_groups": [{"code": {"raw": "W"}, "effective": {"start": "2020-01-01", "end": None}}],
            },
        }
        self.assertTrue(is_filled(output, "company.name"))
        self.assertFalse(is_filled(output, "company.ein"))
        self.assertTrue(is_filled(output, "contact.address"))
        self.assertFalse(is_filled(output, "contact.phone"))
        self.assertTrue(is_filled(output, "tax_ids.tax_id"))
        self.assertFalse(is_filled(output, "tax_ids.name"))
        self.assertFalse(is_filled(output, "work_locations.code"))
        self.assertTrue(is_filled(output, "pay_groups.code"))
        self.assertTrue(is_filled(output, "pay_groups.effective.start"))
        self.assertFalse(is_filled(output, "pay_groups.effective.end"))


if __name__ == "__main__":
    unittest.main()
