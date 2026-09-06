"""Verify an imported data directory and generate PDFs without changing quotes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storage_root", type=Path)
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    root = args.storage_root.resolve()
    from quote_backup import verify
    original = verify(root / "data")
    os.environ["QUOTE_TOOL_WEB"] = "0"
    os.environ["QUOTE_TOOL_STORAGE_ROOT"] = str(root)
    from app import Quote, app, init_db, load_settings, UPLOAD_DIR
    from pdf_generator import build_quote_pdf
    from pypdf import PdfReader
    if args.initialize:
        init_db()
    assert verify(root / "data") == original, "Migration changed original data"
    checked = 0
    pages = 0
    sample_saved = False
    with app.app_context(), tempfile.TemporaryDirectory(dir=root) as temporary:
        settings = load_settings()
        for quote in Quote.query.order_by(Quote.id).all():
            payload = quote.to_dict()
            output = Path(temporary) / "quote.pdf"
            build_quote_pdf(payload, output, settings, upload_root=UPLOAD_DIR)
            with output.open("rb") as handle:
                page_count = len(PdfReader(handle).pages)
            attachment_pages = 0
            for filename in payload["attachments"]:
                with (UPLOAD_DIR / payload["quote_number"] / filename).open("rb") as handle:
                    attachment_pages += len(PdfReader(handle).pages)
            assert page_count >= attachment_pages + 2, "PDF is missing quote or terms pages"
            if not sample_saved and payload["attachments"]:
                shutil.copy2(output, root / "verification-sample.pdf")
                sample_saved = True
            checked += 1
            pages += page_count
    assert checked == original["tables"]["quote"]["count"]
    assert verify(root / "data") == original, "PDF checks changed imported records/files"
    print(json.dumps({"verified": True, "pdfs_checked": checked, "total_pdf_pages": pages,
                      "attachment_records": original["tables"]["attachment"]["count"]}))


if __name__ == "__main__":
    main()
