from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from storage_lock import storage_lock


class StorageLockTests(unittest.TestCase):
    def test_other_process_times_out_then_can_acquire_after_release(self):
        with tempfile.TemporaryDirectory() as folder:
            command = [sys.executable, "-c", """
import sys
from storage_lock import storage_lock
try:
    with storage_lock(sys.argv[1], timeout=0.15):
        pass
except TimeoutError:
    raise SystemExit(23)
""", folder]
            with storage_lock(folder):
                self.assertEqual(subprocess.run(command, timeout=10).returncode, 23)
            self.assertEqual(subprocess.run(command, timeout=10).returncode, 0)

    def test_exception_releases_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                with storage_lock(Path(folder)):
                    raise ValueError("synthetic failure")
            with storage_lock(folder, timeout=0.1):
                pass
