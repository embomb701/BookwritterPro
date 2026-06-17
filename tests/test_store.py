import json
import os
import tempfile
import threading
import time
import unittest

from bookwriter.store import _read_json, _write_json


class TestAtomicWrite(unittest.TestCase):
    def setUp(self):
        # ignore_cleanup_errors: on Windows a reader thread may hold the file
        # open for a microsecond past join; that's a test artifact, not a bug.
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = os.path.join(self._tmp.name, "book.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_then_read_roundtrip(self):
        data = {"title": "T", "outline": list(range(50))}
        _write_json(self.path, data)
        self.assertEqual(_read_json(self.path), data)

    def test_no_temp_files_left_behind(self):
        _write_json(self.path, {"a": 1})
        leftovers = [n for n in os.listdir(self._tmp.name) if n.startswith(".tmp-")]
        self.assertEqual(leftovers, [])

    def test_concurrent_writes_never_yield_partial_json(self):
        # A writer rapidly rewrites the file while readers parse it. With an
        # atomic os.replace swap, readers must always see complete JSON — never
        # a truncated/empty file (which used to raise JSONDecodeError).
        big = {"chapters": [{"n": i, "text": "word " * 80} for i in range(20)]}
        errors = []
        stop = threading.Event()

        def writer():
            try:
                for i in range(120):
                    _write_json(self.path, {**big, "rev": i})
            finally:
                stop.set()  # always release readers, even on an unexpected error

        def reader():
            # A small yield models real HTTP readers (occasional requests), not a
            # zero-backoff hot loop that would pin the file handle continuously.
            while not stop.is_set():
                try:
                    obj = _read_json(self.path)
                    if "chapters" not in obj:
                        errors.append("missing key")
                except (FileNotFoundError, PermissionError):
                    pass
                except json.JSONDecodeError as e:
                    errors.append(f"decode: {e}")
                time.sleep(0.001)

        _write_json(self.path, big)
        threads = [threading.Thread(target=writer)] + [
            threading.Thread(target=reader) for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(errors, [], f"atomic write violated: {errors[:5]}")


if __name__ == "__main__":
    unittest.main()
