"""Shared adapter helpers: one-time code reports and per-line readers."""
import unittest

from normalization.adapters._common import CodeTable, Collector, Reader, line_readers, nonzero
from normalization.canonical import PaymentMethod

TABLE = CodeTable("payments.type_name", PaymentMethod, {"Check": PaymentMethod.CHECK}, "evidence", kind="label")


class CodeOnceChecks(unittest.TestCase):
    def test_unknown_value_is_reported_the_first_time_only(self):
        issues = Collector()
        first = issues.code_once(TABLE, "Pay Card", "a", "k1")
        second = issues.code_once(TABLE, "Pay Card", "b", "k2")
        self.assertEqual(first, second)
        self.assertEqual(first.value, PaymentMethod.UNKNOWN)
        self.assertEqual([issue.source_path for issue in issues.issues], ["a"])

    def test_known_and_blank_values_report_nothing(self):
        issues = Collector()
        self.assertEqual(issues.code_once(TABLE, "Check", "a", "k").value, PaymentMethod.CHECK)
        self.assertIsNone(issues.code_once(TABLE, None, "a", "k"))
        self.assertEqual(issues.issues, [])

    def test_each_table_keeps_its_own_record(self):
        other = CodeTable("other.type_name", PaymentMethod, {}, "evidence", kind="label")
        issues = Collector()
        issues.code_once(TABLE, "Pay Card", "a", "k")
        issues.code_once(other, "Pay Card", "b", "k")
        self.assertEqual(len(issues.issues), 2)


class LineReaderChecks(unittest.TestCase):
    def test_each_line_keeps_its_own_leftovers(self):
        r = Reader({"lines": [{"code": "A", "memo": 1}, {"code": "B"}], "other": 2}, "rec[0]")
        lines = line_readers(r, "lines")
        self.assertEqual([line.get("code") for line in lines], ["A", "B"])
        self.assertEqual(lines[0].unmapped(), {"rec[0].lines[0].memo": 1})
        self.assertEqual(r.unmapped(), {"rec[0].other": 2})

    def test_null_is_consumed_and_a_non_list_is_left_in_unmapped(self):
        r = Reader({"taxes": None, "earnings": "bad"})
        self.assertEqual(line_readers(r, "taxes"), [])
        self.assertEqual(line_readers(r, "earnings"), [])
        self.assertEqual(r.unmapped(), {"earnings": "bad"})


class NonzeroChecks(unittest.TestCase):
    def test_only_real_amounts_count(self):
        self.assertEqual([nonzero(v) for v in (None, "", 0, 0.0, 0.01, "12", -5)],
                         [False, False, False, False, True, True, True])


if __name__ == "__main__":
    unittest.main()
