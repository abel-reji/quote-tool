"""Cross-process storage coordination for requests and consistent backups."""
from contextlib import contextmanager
import os
from pathlib import Path
import time


@contextmanager
def storage_lock(root, timeout=20):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / "storage.lock").open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
        else:
            import fcntl
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("Quote storage is busy. Please retry shortly.") from None
                time.sleep(0.05)
        yield
    finally:
        if locked:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def install_storage_lock(app, root):
    from flask import g, jsonify, request

    @app.before_request
    def acquire_storage():
        if request.endpoint in {"static", "web_login", "web_logout"}:
            return None
        lock = storage_lock(root)
        try:
            lock.__enter__()
        except TimeoutError as error:
            return jsonify(status="error", message=str(error)), 503, {"Retry-After": "5"}
        g.quote_storage_lock = lock

    @app.teardown_request
    def release_storage(error):
        lock = g.pop("quote_storage_lock", None)
        if lock is not None:
            lock.__exit__(None, None, None)
