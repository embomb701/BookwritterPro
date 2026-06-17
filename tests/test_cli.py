import contextlib
import io
import os
import tempfile
import unittest

from bookwriter.cli import main


@contextlib.contextmanager
def _quiet():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


class TestCLI(unittest.TestCase):
    def test_profiles(self):
        with _quiet() as buf:
            rc = main(["profiles"])
        self.assertEqual(rc, 0)
        self.assertIn("balanced", buf.getvalue())

    def test_generate_mock_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _quiet():
                rc = main(["generate", "--premise", "a test", "--chapters", "2",
                           "--words", "120", "--project", tmp, "--mock"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(tmp, "manuscript.md")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "cost.json")))

    def test_plan_then_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _quiet():
                self.assertEqual(main(["plan", "--premise", "x", "--chapters", "2",
                                       "--project", tmp, "--mock"]), 0)
                rc = main(["report", "--project", tmp])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(tmp, "book.json")))


if __name__ == "__main__":
    unittest.main()
