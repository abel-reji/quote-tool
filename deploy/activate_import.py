"""One-time Bluehost cutover. Preserves the original active directory for rollback."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quote_backup import _snapshot, audit, verify
from storage_lock import storage_lock

ROOT = Path("/home3/finvestc/quote-tool-private")
CANDIDATE = ROOT / "activation-20260906" / "data"
ROLLBACK = ROOT / "pre-activation-20260906"


def main():
    os.umask(0o077)
    assert ROOT.resolve() == ROOT and not ROOT.is_symlink()
    for path in (CANDIDATE, ROLLBACK, ROOT / "data"):
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
    config = json.loads((ROOT / "web-config.json").read_text())
    assert Path(config["storage_root"]).resolve() == ROOT
    assert config.get("allow_reference_cgi") is True
    expected = verify(CANDIDATE)
    assert expected["tables"]["quote"]["count"] == 78
    assert not ROLLBACK.exists(), "Prior cutover exists; inspect instead of overwriting"
    maintenance = ROOT / "maintenance.flag"
    with maintenance.open("x") as handle:
        handle.write("Verified import cutover\n")
    moved_old = False
    moved_new = False
    try:
        with storage_lock(ROOT, timeout=45):
            assert audit(ROOT / "data" / "quotes.db")[0]["quote"]["count"] == 0, "Active quotes exist; do not overwrite"
            ROLLBACK.mkdir(mode=0o700)
            # The same lock is already held; the public snapshot wrapper would re-lock.
            _snapshot(ROOT / "data", ROLLBACK / "snapshot")
            try:
                (ROOT / "data").rename(ROLLBACK / "data")
                moved_old = True
                CANDIDATE.rename(ROOT / "data")
                moved_new = True
                assert verify(ROOT / "data") == expected
            except BaseException:
                if moved_new:
                    (ROOT / "data").rename(CANDIDATE)
                if moved_old:
                    (ROLLBACK / "data").rename(ROOT / "data")
                raise
        # Keep maintenance enabled for the final active-path validation.
        print(json.dumps({"activated": True, "quotes": 78, "maintenance": True,
                          "rollback": str(ROLLBACK / "data")}))
    except BaseException:
        # On uncertain failure, keep maintenance enabled rather than exposing partial data.
        print("Cutover stopped; maintenance remains enabled. Inspect before reopening.", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
