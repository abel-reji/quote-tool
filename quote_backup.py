"""Verified, coordinated snapshots. Never changes quote data or overwrites a destination."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
from storage_lock import storage_lock


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Snapshot path escapes the data directory.")
    return path


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def audit(database, columns=None):
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed.")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Database contains broken foreign keys.")
        result = {}
        for table in ("quote", "line_item", "attachment"):
            actual = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            selected = columns[table]["columns"] if columns else actual
            if not selected or not set(selected).issubset(actual):
                raise ValueError("Database schema does not match the snapshot.")
            projection = ", ".join('"' + name.replace('"', '""') + '"' for name in selected)
            rows = connection.execute(f'SELECT {projection} FROM "{table}" ORDER BY id').fetchall()
            digest = hashlib.sha256(json.dumps(rows, ensure_ascii=True, allow_nan=False).encode()).hexdigest()
            result[table] = {"columns": selected, "count": len(rows), "sha256": digest}
        numbers = [row[0] for row in connection.execute("SELECT quote_number FROM quote")]
        if any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,49}", n) for n in numbers):
            raise ValueError("Legacy quote numbers include unsupported characters; review before migrating.")
        attachments = []
        for number, filename in connection.execute("SELECT q.quote_number, a.filename FROM attachment a JOIN quote q ON q.id = a.quote_id ORDER BY a.id"):
            if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
                raise ValueError("Unsafe attachment filename in database.")
            attachments.append(f"uploads/{number}/{filename}")
        return result, attachments


def snapshot(source, destination):
    with storage_lock(source.resolve().parent, timeout=30):
        return _snapshot(source, destination)


def _snapshot(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Snapshot must be separate from the source.")
    if destination.exists():
        raise ValueError("Destination already exists; nothing was overwritten.")
    database = source / "quotes.db"
    if not database.is_file():
        raise ValueError("Source quotes.db was not found.")
    destination.mkdir(parents=True, mode=0o700)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(destination / "quotes.db")) as backup:
            original.backup(backup)
    tables, attachments = audit(destination / "quotes.db")
    files = list(dict.fromkeys(attachments))
    files.extend(name for name in ("settings.json", "customers.json") if (source / name).is_file())
    hashes = {}
    for name in files:
        original = inside(source, name)
        if not original.is_file():
            raise ValueError("A referenced attachment is missing; snapshot is incomplete.")
        target = inside(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(original, target)
        hashes[name] = file_hash(target)
        if file_hash(original) != hashes[name]:
            raise ValueError("A source file changed during the snapshot; close the app and retry.")
    manifest = {"version": 1, "tables": tables, "files": hashes}
    (destination / "snapshot-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Re-read the source to catch quote edits made while attachments were being copied.
    if audit(database)[0] != tables:
        raise ValueError("Source database changed during the snapshot; close the app and retry.")
    verify(destination)
    return manifest


def verify(directory):
    directory = directory.resolve()
    manifest = json.loads((directory / "snapshot-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise ValueError("Unknown snapshot version.")
    tables, attachments = audit(directory / "quotes.db", manifest["tables"])
    if tables != manifest["tables"]:
        raise ValueError("Database records differ from the snapshot.")
    if not set(attachments).issubset(manifest["files"]):
        raise ValueError("Attachment manifest is incomplete.")
    for name, expected in manifest["files"].items():
        path = inside(directory, name)
        if not path.is_file() or file_hash(path) != expected:
            raise ValueError("Snapshot file missing or changed.")
    return manifest


def restore(source, destination):
    source, destination = source.resolve(), destination.resolve()
    manifest = verify(source)
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Restore requires a new, separate destination.")
    destination.mkdir(parents=True, mode=0o700)
    for name in ["quotes.db", "snapshot-manifest.json", *manifest["files"]]:
        target = inside(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(inside(source, name), target)
    return verify(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "verify", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    if args.action != "verify" and args.destination is None:
        parser.error("A destination is required.")
    if args.action == "verify":
        manifest = verify(args.source)
    else:
        manifest = {"snapshot": snapshot, "restore": restore}[args.action](args.source, args.destination)
    counts = {table: info["count"] for table, info in manifest["tables"].items()}
    print(json.dumps({"verified": True, "counts": counts, "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
