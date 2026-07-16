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
