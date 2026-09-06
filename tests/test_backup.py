from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

from quote_backup import snapshot, restore, verify


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        with closing(sqlite3.connect(self.source / "quotes.db")) as db, db:
            db.executescript('''
                CREATE TABLE quote (id INTEGER PRIMARY KEY, quote_number TEXT, quote_total REAL);
                CREATE TABLE line_item (id INTEGER PRIMARY KEY, quote_id INTEGER REFERENCES quote(id), item_name TEXT);
                CREATE TABLE attachment (id INTEGER PRIMARY KEY, quote_id INTEGER REFERENCES quote(id), filename TEXT);
                INSERT INTO quote VALUES (1, 'Q-1', 125.50);
                INSERT INTO line_item VALUES (1, 1, 'Synthetic pump');
                INSERT INTO attachment VALUES (1, 1, 'annex.pdf');
            ''')
        folder = self.source / "uploads" / "Q-1"
        folder.mkdir(parents=True)
        (folder / "annex.pdf").write_bytes(b"Synthetic PDF")
        (self.source / "settings.json").write_text('{"user": {}}')

    def test_snapshot_restore_preserves_records_files_and_source(self):
        original = (self.source / "quotes.db").read_bytes()
        backup = self.root / "backup"
        manifest = snapshot(self.source, backup)
        self.assertEqual(manifest["tables"]["quote"]["count"], 1)
        restored = self.root / "restored"
        self.assertEqual(restore(backup, restored), manifest)
        self.assertEqual((restored / "uploads/Q-1/annex.pdf").read_bytes(), b"Synthetic PDF")
        self.assertEqual((self.source / "quotes.db").read_bytes(), original)
        with closing(sqlite3.connect(restored / "quotes.db")) as db, db:
            db.execute("ALTER TABLE line_item ADD COLUMN components JSON")
        self.assertEqual(verify(restored), manifest)

    def test_corruption_and_overwrites_are_rejected(self):
        backup = self.root / "backup"
        snapshot(self.source, backup)
        with self.assertRaises(ValueError):
            snapshot(self.source, backup)
        with self.assertRaises(ValueError):
            restore(backup, self.source)
        (backup / "uploads/Q-1/annex.pdf").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            verify(backup)

    def test_changed_records_are_rejected(self):
        backup = self.root / "backup"
        snapshot(self.source, backup)
        with closing(sqlite3.connect(backup / "quotes.db")) as db, db:
            db.execute("UPDATE quote SET quote_total=1")
        with self.assertRaises(ValueError):
            verify(backup)

    def test_missing_and_unsafe_attachments_fail_closed(self):
        (self.source / "uploads/Q-1/annex.pdf").unlink()
        with self.assertRaises(ValueError):
            snapshot(self.source, self.root / "missing")
        with closing(sqlite3.connect(self.source / "quotes.db")) as db, db:
            db.execute("UPDATE attachment SET filename='../private'")
        with self.assertRaises(ValueError):
            snapshot(self.source, self.root / "unsafe")
