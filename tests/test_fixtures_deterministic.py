"""The committed fixtures must be exactly what the generator produces."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

from _fixtures import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_fixtures  # noqa: E402


class FixtureDeterminismChecks(unittest.TestCase):
    def test_default_seed_reproduces_committed_files_byte_for_byte(self):
        for relative, content in generate_fixtures.generate().items():
            with self.subTest(file=relative):
                self.assertEqual((FIXTURES / relative).read_text(encoding="utf-8"), content)

    def test_check_mode_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(generate_fixtures.main(["--check"]), 0)

    def test_generation_is_a_pure_function_of_the_seed(self):
        self.assertEqual(generate_fixtures.generate(7), generate_fixtures.generate(7))
        self.assertNotEqual(generate_fixtures.generate(7), generate_fixtures.generate())

    def test_fixture_files_contain_no_live_identifiers(self):
        for path in FIXTURES.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("myisolved.com", text)
                self.assertNotIn("saashr.com", text)


if __name__ == "__main__":
    unittest.main()
