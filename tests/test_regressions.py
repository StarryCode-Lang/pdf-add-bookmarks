import sys
from pathlib import Path
import subprocess
import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_bookmarks as app

SCRIPT = Path(app.__file__)


def run(source, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(source), *map(str, args)],
                          capture_output=True, text=True, timeout=120)


def test_explicit_type_changes_output(tmp_path):
    source = tmp_path / "types.pdf"
    with fitz.open() as doc:
        p = doc.new_page()
        p.insert_text((60, 80), "Chapter 1 Introduction", fontsize=18)
        p.insert_text((60, 130), "2000年试题 示例", fontname="china-s", fontsize=18)
        doc.save(source)
    for profile, expected in [("textbook", "Chapter 1 Introduction"), ("exam", "2000年试题 示例")]:
        output = tmp_path / (profile + ".pdf")
        result = run(source, "--type", profile, "-o", output)
        assert result.returncode == 0, result.stdout
        with fitz.open(output) as doc:
            assert [row[1] for row in doc.get_toc()] == [expected]


def test_article_and_slide_profiles():
    assert app.match_heading("Abstract", pdf_type="article")
    assert app.match_heading("Chapter 1 Methods", pdf_type="article") is None
    assert app.match_heading("Chapter 1 Methods", pdf_type="slides") is None
    assert app.match_heading("一、基本概念", pdf_type="slides")


def test_repeated_headers_and_body_sentences():
    pages = [(i, f"Chapter 9 Running Header\nChapter {i} Unique Title\n1. This is a body sentence.\nFooter") for i in range(1, 6)]
    headings = app.headings_from_pages(pages, set())
    assert [h["title"] for h in headings] == [f"Chapter {i} Unique Title" for i in range(1, 6)]


@pytest.mark.requires_tesseract
def test_mixed_pdf_includes_scanned_page_and_preserves_pixels(tmp_path):
    source = tmp_path / "mixed.pdf"
    with fitz.open() as doc:
        p = doc.new_page()
        p.insert_text((60, 80), "Chapter 1 Introduction", fontsize=24)
        p.insert_text((60, 130), "A text page with enough useful extractable content.", fontsize=12)
        with fitz.open(Path(__file__).parent / "fixtures" / "scanned.pdf") as scanned:
            doc.insert_pdf(scanned, from_page=1, to_page=1)
        doc.save(source)
    output = tmp_path / "out.pdf"
    result = run(source, "--lang", "eng", "--workers", "1", "-o", output)
    assert result.returncode == 0, result.stdout
    assert "1/2 pages" in result.stdout
    with fitz.open(output) as doc:
        assert doc.get_toc() == [[1, "Chapter 1 Introduction", 1], [1, "Chapter 2 Methods", 2]]
    assert app.verify_content(source, output)


@pytest.mark.parametrize("option,value,message", [("--workers", "0", "positive"), ("--toc", "missing.txt", "not found")])
def test_invalid_options_no_traceback(tmp_path, option, value, message):
    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    output = tmp_path / "out.pdf"
    result = run(source, option, value, "-o", output)
    assert result.returncode == 1
    assert message in result.stdout
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_corrupt_pdf_and_same_path(tmp_path):
    source = tmp_path / "bad.pdf"
    source.write_bytes(b"invalid PDF")
    result = run(source)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    result = run(source, "-o", source)
    assert result.returncode == 1
    assert source.read_bytes() == b"invalid PDF"


@pytest.mark.requires_tesseract
def test_missing_language_fails_without_output(tmp_path):
    source = Path(__file__).parent / "fixtures" / "scanned.pdf"
    output = tmp_path / "out.pdf"
    result = run(source, "--lang", "nonexistent", "-o", output)
    assert result.returncode == 1
    assert "Missing OCR languages" in result.stdout
    assert not output.exists()


def test_out_of_range_toc_fails(tmp_path):
    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    toc = tmp_path / "toc.txt"
    toc.write_text("Title 99", encoding="utf-8")
    result = run(source, "--toc", toc, "-o", tmp_path / "out.pdf")
    assert result.returncode == 1
    assert "out of range" in result.stdout


def test_analyze_roundtrip_preserves_hierarchy(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open(Path(__file__).parent / "fixtures" / "english_text.pdf") as doc:
        doc.save(source)
    result = run(source, "--analyze")
    assert result.returncode == 0, result.stdout
    output = tmp_path / "out.pdf"
    result = run(source, "--toc", tmp_path / "source_suggested_toc.txt", "-o", output)
    assert result.returncode == 0, result.stdout
    with fitz.open(output) as doc:
        assert [row[0] for row in doc.get_toc()] == [1, 2, 3, 1, 2, 3]


def test_failed_verification_preserves_existing_output(tmp_path, monkeypatch):
    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    output = tmp_path / "out.pdf"
    output.write_bytes(b"existing user output")
    monkeypatch.setattr(app, "verify_content", lambda *_: False)
    with pytest.raises(ValueError, match="verification failed"):
        app.add_bookmarks(source, [(1, "Title", -1)], output)
    assert output.read_bytes() == b"existing user output"
    assert list(tmp_path.iterdir()) == [output]
