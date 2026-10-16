"""The direct deposit coverage map: complete, evidenced, and consistent with the golden outputs."""
import unittest

from _fixtures import expected_output, resolve_evidence, schema
from normalization.bundle import PROVIDER_SPECS
from normalization.deposit_field_map import (
    FIELD_MAP,
    SECTION_FIELDS,
    canonical_fields,
    is_filled,
    section,
)
from normalization.field_map import MAPPED, NOT_MAPPED_YET, NOT_OFFERED, STATUSES

PROVIDERS = tuple(PROVIDER_SPECS)
NESTED_DEFS = {"allocation": "Allocation", "effective": "DateRange"}


def golden_deposits(provider: str) -> list:
    return expected_output(provider, "direct-deposit")["direct_deposits"]


class DepositFieldMapChecks(unittest.TestCase):
    def test_every_provider_has_an_entry_for_every_row(self):
        rows = set(canonical_fields())
        self.assertEqual(len(canonical_fields()), 11)
        self.assertEqual(set(FIELD_MAP), set(PROVIDERS))
        for provider, entries in FIELD_MAP.items():
            with self.subTest(provider=provider):
                self.assertEqual(set(entries), rows)

    def test_rows_cover_every_value_field_of_the_schema(self):
        defs = schema()["$defs"]
        expected = set()
        for name in defs["DirectDeposit"]["properties"]:
            if name in ("key", "employee_key", "company_key", "source", "unmapped"):
                continue
            if name in NESTED_DEFS:
                expected.update(f"{name}.{child}" for child in defs[NESTED_DEFS[name]]["properties"])
            else:
                expected.add(name)
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
            deposits = golden_deposits(provider)
            for field, entry in entries.items():
                if entry.status == MAPPED:
                    continue
                with self.subTest(provider=provider, field=field, status=entry.status):
                    self.assertFalse(any(is_filled(deposit, field) for deposit in deposits))

    def test_mapped_rows_are_filled_or_explain_the_gap(self):
        for provider, entries in FIELD_MAP.items():
            deposits = golden_deposits(provider)
            for field, entry in entries.items():
                if entry.status != MAPPED:
                    continue
                filled = sum(1 for deposit in deposits if is_filled(deposit, field))
                with self.subTest(provider=provider, field=field):
                    if entry.sample_gap:
                        self.assertEqual(filled, 0, "sample_gap is set but the sample fills the field")
                    else:
                        self.assertGreater(filled, 0, "mapped field is never filled; add sample_gap")

    def test_is_filled_reads_top_level_and_nested_rows(self):
        deposit = {"bank_name": "Bank", "priority": None, "allocation": {"method": {"raw": "F"}, "amount": None},
                   "effective": None}
        self.assertTrue(is_filled(deposit, "bank_name"))
        self.assertFalse(is_filled(deposit, "priority"))
        self.assertTrue(is_filled(deposit, "allocation.method"))
        self.assertFalse(is_filled(deposit, "allocation.amount"))
        self.assertFalse(is_filled(deposit, "effective.start"))


if __name__ == "__main__":
    unittest.main()
