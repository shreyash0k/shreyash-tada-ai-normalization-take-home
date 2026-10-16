"""The coverage field map: complete, evidenced, and consistent with the golden outputs."""
import unittest

from _fixtures import expected_output, resolve_evidence, schema
from normalization.bundle import PROVIDER_SPECS
from normalization.field_map import (
    FIELD_MAP,
    LIST_KINDS,
    MAPPED,
    NOT_MAPPED_YET,
    NOT_OFFERED,
    SCALAR_FIELDS,
    STATUSES,
    canonical_fields,
    is_filled,
)

PROVIDERS = tuple(PROVIDER_SPECS)
KIND_DEFS = {"addresses": "Address", "phones": "Phone", "emails": "Email"}


class FieldMapChecks(unittest.TestCase):
    def test_every_provider_has_an_entry_for_every_row(self):
        rows = set(canonical_fields())
        self.assertEqual(len(canonical_fields()), 52)
        self.assertEqual(set(FIELD_MAP), set(PROVIDERS))
        for provider, entries in FIELD_MAP.items():
            with self.subTest(provider=provider):
                self.assertEqual(set(entries), rows)

    def test_scalar_rows_match_the_schema_exactly(self):
        defs = schema()["$defs"]
        for section, names in SCALAR_FIELDS.items():
            with self.subTest(section=section):
                self.assertEqual(tuple(defs[section.capitalize()]["properties"]), names)

    def test_list_rows_use_schema_kinds(self):
        defs = schema()["$defs"]
        for list_name, kinds in LIST_KINDS.items():
            enum = defs[KIND_DEFS[list_name]]["properties"]["kind"]["enum"]
            for kind in kinds:
                with self.subTest(field=f"contact.{list_name}[{kind}]"):
                    self.assertIn(kind, enum)

    def test_every_kind_in_golden_output_has_a_row(self):
        for provider in PROVIDERS:
            for employee in expected_output(provider)["employees"]:
                for list_name, kinds in LIST_KINDS.items():
                    for item in employee["contact"][list_name]:
                        with self.subTest(provider=provider, list=list_name, kind=item["kind"]):
                            self.assertIn(item["kind"], kinds)

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
            employees = expected_output(provider)["employees"]
            for field, entry in entries.items():
                if entry.status == MAPPED:
                    continue
                with self.subTest(provider=provider, field=field, status=entry.status):
                    self.assertFalse(any(is_filled(employee, field) for employee in employees))

    def test_mapped_rows_are_filled_or_explain_the_gap(self):
        for provider, entries in FIELD_MAP.items():
            employees = expected_output(provider)["employees"]
            for field, entry in entries.items():
                if entry.status != MAPPED:
                    continue
                filled = sum(1 for employee in employees if is_filled(employee, field))
                with self.subTest(provider=provider, field=field):
                    if entry.sample_gap:
                        self.assertEqual(filled, 0, "sample_gap is set but the sample fills the field")
                    else:
                        self.assertGreater(filled, 0, "mapped field is never filled; add sample_gap")

    def test_is_filled_reads_scalar_and_list_rows(self):
        employee = {
            "person": {"first_name": "Avery"},
            "employment": {"status": None},
            "contact": {"addresses": [{"kind": "home"}], "phones": [], "emails": []},
        }
        self.assertTrue(is_filled(employee, "person.first_name"))
        self.assertFalse(is_filled(employee, "employment.status"))
        self.assertTrue(is_filled(employee, "contact.addresses[home]"))
        self.assertFalse(is_filled(employee, "contact.addresses[mailing]"))


if __name__ == "__main__":
    unittest.main()
