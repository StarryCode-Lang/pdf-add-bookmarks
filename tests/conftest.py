from pathlib import Path
import sys

# Auto-generate PDF fixtures if any are missing.
# Keeps the repository free of generated binary files while still making
# `pytest` work out of the box after a fresh clone.

def _ensure_fixtures():
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    pdf_names = [
        "chinese_text.pdf",
        "english_text.pdf",
        "single_page.pdf",
        "no_headings.pdf",
        "images_only.pdf",
        "large.pdf",
    ]
    if all((fixtures_dir / name).exists() for name in pdf_names):
        return

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_test_pdfs", Path(__file__).resolve().parent / "generate_test_pdfs.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_test_pdfs"] = module
    spec.loader.exec_module(module)
    module.main()


_ensure_fixtures()

# Portable two-page image-only fixture, generated from embedded PDF fonts.
def _ensure_scanned_fixture():
    import fitz
    path = Path(__file__).parent / "fixtures" / "scanned.pdf"
    with fitz.open() as output:
        for title in ["Chapter 1 Introduction", "Chapter 2 Methods"]:
            with fitz.open() as source:
                page = source.new_page(width=595, height=842)
                page.insert_text((60, 80), title, fontsize=24)
                page.insert_text((60, 130), "This is a reproducible image-only OCR test document.", fontsize=12)
                pix = page.get_pixmap(dpi=160)
                target = output.new_page(width=595, height=842)
                target.insert_image(target.rect, stream=pix.tobytes("png"))
        output.save(path)

_ensure_scanned_fixture()


def pytest_collection_modifyitems(items):
    import pytest
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from add_bookmarks import ensure_tesseract
    import pytesseract
    ready = ensure_tesseract() and {"eng", "chi_sim"} <= set(pytesseract.get_languages())
    if not ready:
        for item in items:
            if "requires_tesseract" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Tesseract eng/chi_sim not installed"))
