"""Offline web setup. Run with the same Python environment as the hosted app."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets

from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure", help="Create a new private credentials file")
    configure.add_argument("--config", required=True, type=Path)
    configure.add_argument("--storage-root", required=True, type=Path)
    configure.add_argument("--public-root", required=True, type=Path)
    configure.add_argument("--host", required=True)
    configure.add_argument("--username", required=True)
    initialize = commands.add_parser("init", help="Initialize only the configured web database")
    initialize.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    if args.command == "configure":
        storage, public = args.storage_root.resolve(), args.public_root.resolve()
        if storage.is_relative_to(public) or public.is_relative_to(storage) or config_path.is_relative_to(public):
            parser.error("Private storage/configuration must be outside the public tree.")
        if config_path.exists():
            parser.error("Configuration already exists; it will not be overwritten.")
        if not args.username.strip() or any(char in args.host for char in "/\\:@* \t\r\n") or not args.host:
            parser.error("Provide a username and a bare hostname.")
        password = getpass.getpass("New web password (at least 14 characters): ")
        if not 14 <= len(password) <= 1024:
            parser.error("Password must contain 14 to 1024 characters.")
        if password != getpass.getpass("Confirm web password: "):
            parser.error("Passwords do not match.")
        storage.mkdir(parents=True, exist_ok=True, mode=0o700)
        config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        config = {
            "host": args.host, "username": args.username.strip(),
            "secret_key": secrets.token_urlsafe(48),
            "password_hash": generate_password_hash(password, method="pbkdf2:sha256:1000000"),
            "storage_root": str(storage), "public_root": str(public),
            "allow_reference_cgi": False,
        }
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(config, handle, indent=2)
        print(f"Created private configuration: {config_path}")
        print("No database or live quote data was copied. Run init next.")
    else:
        os.environ["QUOTE_TOOL_WEB"] = "1"
        os.environ["QUOTE_TOOL_CONFIG"] = str(config_path)
        from app import DB_FILE, ensure_settings_file, init_db
        init_db()
        ensure_settings_file()
        print(f"Web database initialized: {DB_FILE}")


if __name__ == "__main__":
    main()
