"""The payroll coverage map: complete, evidenced, and consistent with the golden outputs."""
import unittest

from _fixtures import expected_output, resolve_evidence, schema
from normalization.bundle import PROVIDER_SPECS
from normalization.field_map import MAPPED, NOT_MAPPED_YET, NOT_OFFERED, STATUSES
from normalization.payroll_field_map import (
    FIELD_MAP,
    SECTION_FIELDS,
    canonical_fields,
    is_filled,
    section,
)

PROVIDERS = tuple(PROVIDER_SPECS)
SKIP_RUN = {"key", "company_key", "source", "unmapped"}
SKIP_CHECK = {"key", "employee_key", "company_key", "source", "unmapped", "pay_run_key"}
LINE_DEFS = {"earnings": "EarningLine", "taxes": "TaxLine", "deductions": "DeductionLine",
             "employer_contributions": "ContributionLine", "payments": "PaymentLine"}


def golden_payroll(provider: str) -> dict:
    return expected_output(provider, "payroll")


class PayrollFieldMapChecks(unittest.TestCase):
    def test_every_provider_has_an_entry_for_every_row(self):
        rows = set(canonical_fields())
        self.assertEqual(len(canonical_fields()), 34)
        self.assertEqual(set(FIELD_MAP), set(PROVIDERS))
        for provider, entries in FIELD_MAP.items():
            with self.subTest(provider=provider):
                self.assertEqual(set(entries), rows)

    def test_rows_cover_every_value_field_of_the_schema(self):
        defs = schema()["$defs"]
        expected = set()
        for name, prefix, skip in (("PayRun", "pay_run", SKIP_RUN), ("Paycheck", "paycheck", SKIP_CHECK)):
            for field in defs[name]["properties"]:
                if field in skip:
                    continue
                if field == "period":
                    expected.update(f"{prefix}.period.{child}" for child in defs["DateRange"]["properties"])
                elif field in LINE_DEFS:
                    for child in defs[LINE_DEFS[field]]["properties"]:
                        if child != "unmapped":
                            expected.add(f"{field}.{child}")
                else:
                    expected.add(f"{prefix}.{field}")
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
            payroll = golden_payroll(provider)
            for field, entry in entries.items():
                if entry.status == MAPPED:
                    continue
                with self.subTest(provider=provider, field=field, status=entry.status):
                    self.assertFalse(is_filled(payroll, field))

    def test_mapped_rows_are_filled_or_explain_the_gap(self):
        for provider, entries in FIELD_MAP.items():
            payroll = golden_payroll(provider)
            for field, entry in entries.items():
                if entry.status != MAPPED:
                    continue
                with self.subTest(provider=provider, field=field):
                    filled = is_filled(payroll, field)
                    if entry.sample_gap:
                        self.assertFalse(filled, "sample_gap is set but the sample fills the field")
                    else:
                        self.assertTrue(filled, "mapped field is never filled; add sample_gap")

    def test_is_filled_reads_runs_checks_and_lines(self):
        output = {
            "pay_runs": [{"type": {"raw": "R"}, "period": {"start": None, "end": "2026-01-02"}}],
            "paychecks": [{"gross_pay": None, "earnings": [{"code": {"raw": "REG"}, "rate": None}], "taxes": []}],
        }
        self.assertTrue(is_filled(output, "pay_run.type"))
        self.assertFalse(is_filled(output, "pay_run.period.start"))
        self.assertTrue(is_filled(output, "pay_run.period.end"))
        self.assertFalse(is_filled(output, "paycheck.gross_pay"))
        self.assertTrue(is_filled(output, "earnings.code"))
        self.assertFalse(is_filled(output, "earnings.rate"))
        self.assertFalse(is_filled(output, "taxes.code"))


if __name__ == "__main__":
    unittest.main()
