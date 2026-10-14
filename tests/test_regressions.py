import subprocess
import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_bookmarks as app

SCRIPT = Path(app.__file__)


def run(source, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_explicit_type_changes_output(tmp_path):
    source = tmp_path / "types.pdf"
    with fitz.open() as doc:
        p = doc.new_page()
        p.insert_text((60, 80), "Chapter 1 Introduction", fontsize=18)
        p.insert_text((60, 130), "2000年试题 示例", fontname="china-s", fontsize=18)
        doc.save(source)
    for profile, expected in [
        ("textbook", "Chapter 1 Introduction"),
        ("exam", "2000年试题 示例"),
    ]:
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
    pages = [
        (
            i,
            f"Chapter 9 Running Header\nChapter {i} Unique Title\n1. This is a body sentence.\nFooter",
        )
        for i in range(1, 6)
    ]
    headings = app.headings_from_pages(pages, set())
    assert [h["title"] for h in headings] == [
        f"Chapter {i} Unique Title" for i in range(1, 6)
    ]


@pytest.mark.requires_tesseract
def test_mixed_pdf_includes_scanned_page_and_preserves_pixels(tmp_path):
    source = tmp_path / "mixed.pdf"
    with fitz.open() as doc:
        p = doc.new_page()
        p.insert_text((60, 80), "Chapter 1 Introduction", fontsize=24)
        p.insert_text(
            (60, 130),
            "A text page with enough useful extractable content.",
            fontsize=12,
        )
        with fitz.open(Path(__file__).parent / "fixtures" / "scanned.pdf") as scanned:
            doc.insert_pdf(scanned, from_page=1, to_page=1)
        doc.save(source)
    output = tmp_path / "out.pdf"
    result = run(source, "--lang", "eng", "--workers", "1", "-o", output)
    assert result.returncode == 0, result.stdout
    assert "1/2 pages" in result.stdout
    with fitz.open(output) as doc:
        assert doc.get_toc() == [
            [1, "Chapter 1 Introduction", 1],
            [1, "Chapter 2 Methods", 2],
        ]
    assert app.verify_content(source, output)


@pytest.mark.parametrize(
    "option,value,message",
    [("--workers", "0", "positive"), ("--toc", "missing.txt", "not found")],
)
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
    toc.write_text("Title\t99", encoding="utf-8")
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


def test_generate_toc_adds_smaller_bold_titles_and_exports(tmp_path):
    source = tmp_path / "sample.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 80), "Sample Heading", fontname="hebo", fontsize=12)
        for number in range(10):
            page.insert_text(
                (60, 120 + number * 16), "This is plain sample body text.", fontsize=12
            )
        doc.save(source)
    ordinary = run(source, "-o", tmp_path / "ordinary.pdf")
    assert ordinary.returncode == 1
    result = run(source, "--generate-toc", "-o", tmp_path / "generated.pdf")
    assert result.returncode == 0, result.stdout
    assert (tmp_path / "sample_suggested_toc.txt").read_text() == "Sample Heading\t1\n"
    with fitz.open(tmp_path / "generated.pdf") as doc:
        assert doc.get_toc() == [[1, "Sample Heading", 1]]


def test_ocr_worker_limits_native_threads(tmp_path, monkeypatch):
    import os

    import pytesseract

    source = tmp_path / "sample.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(source)
    monkeypatch.setenv("OMP_THREAD_LIMIT", "8")

    def fake_ocr(image, **options):
        assert os.environ["OMP_THREAD_LIMIT"] == "1"
        assert options["timeout"] == 120
        return {"text": []}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_ocr)
    assert app._read_image_page((str(source), 0, "eng", None, False)) == (1, "", [])


def test_json_contract_success_analysis_failure_and_parser(tmp_path):
    import json

    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    for options, ok in [
        (("--json", "-o", tmp_path / "out.pdf"), True),
        (("--json", "--analyze"), True),
        (("--json", "--workers", "0"), False),
        (("--json", "--dpi", "0"), False),
        (("--json", "--unknown-option"), False),
    ]:
        result = run(source, *options)
        data = json.loads(result.stdout)
        assert data["ok"] is ok
        assert result.returncode == (0 if ok else 1)
        if "--analyze" in options:
            assert data["mode"] == "analyze" and data["candidates"] == 1
            assert Path(data["toc"]).is_file()


def test_missing_ocr_is_fatal_or_explicitly_partial(tmp_path, monkeypatch, capsys):
    source = tmp_path / "mixed.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 80), "Chapter 1 Text", fontsize=24)
        with fitz.open(Path(__file__).parent / "fixtures" / "scanned.pdf") as scan:
            doc.insert_pdf(scan, from_page=0, to_page=0)
        doc.save(source)
    monkeypatch.setattr(app, "ensure_tesseract", lambda: False)
    with pytest.raises(ValueError, match="Tesseract"):
        app.read_pages(source)
    warnings = []
    pages, scanned, visual = app.read_pages(
        source, allow_partial=True, warnings=warnings
    )
    assert len(pages) == 2 and not scanned
    assert len(warnings) == 1 and "skipped 1" in warnings[0]
    assert "Warning:" in capsys.readouterr().out


@pytest.mark.parametrize(
    "line", ["ISO 9001", "No page", "Title -1", "Title\t0", "\t12"]
)
def test_ambiguous_or_invalid_toc_rejected(tmp_path, line):
    toc = tmp_path / "toc.txt"
    toc.write_text(line, encoding="utf-8")
    with pytest.raises(ValueError, match="TOC line 1"):
        app.parse_toc_file(toc)


def test_toc_delimiters_and_unlimited_depth(tmp_path):
    toc = tmp_path / "toc.txt"
    toc.write_text(
        "ISO 9001\t1\n  Child  2\n    Grandchild...3\n      Fourth\t4\n        Fifth\t5\n",
        encoding="utf-8",
    )
    entries = app.parse_toc_file(toc)
    assert [h["level"] for h in entries] == [0, 1, 2, 3, 4]
    assert entries[0]["title"] == "ISO 9001"


def test_repeated_child_titles_keep_their_chapter():
    headings = [
        {"title": "Chapter 1 First", "type": "chapter", "page": 1},
        {"title": "Summary", "type": "section", "page": 2},
        {"title": "Chapter 2 Second", "type": "chapter", "page": 3},
        {"title": "Summary", "type": "section", "page": 4},
    ]
    tree = app.build_tree_from_headings(app.filter_headings(headings))
    assert tree == [
        (1, "Chapter 1 First", -1),
        (2, "Summary", 0),
        (3, "Chapter 2 Second", -1),
        (4, "Summary", 2),
    ]


def test_split_heading_rows_and_body_references(tmp_path):
    source = tmp_path / "layout.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 80), "Chapter 1", fontsize=20)
        page.insert_text((60, 120), "A wrapped heading", fontsize=24)
        page.insert_text((60, 149), "continues here", fontsize=24)
        page.insert_text((60, 200), "1.1", fontsize=16)
        page.insert_text((110, 200), "A section title", fontsize=16)
        for i in range(10):
            page.insert_text(
                (60, 240 + i * 20),
                "Chapter 2 is mentioned in normal body text.",
                fontsize=12,
            )
        doc.save(source)
    pages, scan, visual = app.read_pages(source)
    headings = app.headings_from_pages(pages, scan, visual=visual)
    assert [(h["type"], h["title"]) for h in headings] == [
        ("chapter", "Chapter 1 A wrapped heading continues here"),
        ("section", "1.1 A section title"),
    ]


def test_preserves_links_annotations_attachment_and_metadata(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "out.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 80), "Chapter 1 Example", fontsize=24)
        page.insert_link(
            {
                "kind": fitz.LINK_URI,
                "from": fitz.Rect(60, 70, 160, 90),
                "uri": "https://example.com",
            }
        )
        page.add_text_annot((100, 150), "Keep this annotation")
        doc.embfile_add("note.txt", b"Keep this attachment")
        doc.set_metadata({"title": "Preserved title"})
        doc.set_page_labels([{"startpage": 0, "prefix": "P", "style": "D"}])
        doc.save(source)
    app.add_bookmarks(source, [(1, "Example", -1)], output, "full")
    assert app.verify_content(source, output, render=True)
    with fitz.open(output) as doc:
        assert doc.embfile_get("note.txt") == b"Keep this attachment"
        assert doc[0].get_links()[0]["uri"] == "https://example.com"
        assert next(doc[0].annots()).info["content"] == "Keep this annotation"


def test_atomic_output_when_ocr_worker_fails(tmp_path, monkeypatch):
    source = Path(__file__).parent / "fixtures" / "scanned.pdf"

    class BrokenPool:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def map(self, *args):
            raise RuntimeError("OCR timeout")

    monkeypatch.setattr(app, "ProcessPoolExecutor", BrokenPool)
    monkeypatch.setattr(app, "ensure_tesseract", lambda: True)
    import pytesseract

    monkeypatch.setattr(pytesseract, "get_languages", lambda: ["eng"])
    with pytest.raises(RuntimeError, match="OCR timeout"):
        app.read_pages(source, lang="eng")
    assert not list(tmp_path.iterdir())


def test_chapter_mentions_and_partial_words_are_not_headings():
    assert app.match_heading("part of the journey the speed was") is None
    assert app.match_heading("part from a larger to find the difference") is None
    assert app.match_heading("CHAPTER XXIII. ARC LENGTH")
    assert app.match_heading("Appendix A Debugging")
    pages = [(1, "Chapter XV. we found that there was such a func-")]
    assert app.headings_from_pages(pages, {1}, visual={1: []}) == []


def test_repeated_root_titles_on_distinct_pages_remain():
    headings = [{"title": "Summary", "type": "chapter", "page": p} for p in [2, 4]]
    assert len(app.filter_headings(headings)) == 2


def test_json_partial_flag(tmp_path, monkeypatch, capsys):
    import json

    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    monkeypatch.setattr(
        app,
        "read_pages",
        lambda *a: ([(1, "Chapter 1 Text")], set(), {1: ["Chapter 1 Text"]}),
    )

    def partial(*args):
        args[-1].append("Missing OCR languages; skipped 1 scanned page")
        return [(1, "Chapter 1 Text")], set(), {1: ["Chapter 1 Text"]}

    monkeypatch.setattr(app, "read_pages", partial)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            str(source),
            "--json",
            "--allow-partial",
            "-o",
            str(tmp_path / "out.pdf"),
        ],
    )
    assert app.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["partial"] is True and len(result["warnings"]) == 1


def test_changed_content_is_detected(tmp_path):
    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    modified = tmp_path / "changed.pdf"
    with fitz.open(source) as doc:
        doc[0].insert_text((60, 400), "Unexpected new page content")
        doc.save(modified)
    assert not app.verify_content(source, modified)


def test_orphan_subsection_export_matches_pdf_depth(tmp_path):
    source = tmp_path / "appendix.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 80), "Appendix A Debugging", fontsize=24)
        page.insert_text((60, 150), "A.1 Syntax errors", fontsize=18)
        page.insert_text(
            (60, 220),
            "Enough body text to establish the normal font size.",
            fontsize=12,
        )
        doc.save(source)
    result = run(source, "--analyze")
    assert result.returncode == 0
    assert (tmp_path / "appendix_suggested_toc.txt").read_text().splitlines() == [
        "Appendix A Debugging\t1",
        "  A.1 Syntax errors\t1",
    ]


def test_numbered_running_header_with_ocr_punctuation():
    pages = [
        (i, f"“{i} CALCULUS MADE EASY\nCHAPTER {i} UNIQUE TITLE\nNormal body")
        for i in range(1, 6)
    ]
    headings = app.headings_from_pages(pages, set(range(1, 6)), visual={})
    assert [h["title"] for h in headings] == [
        f"CHAPTER {i} UNIQUE TITLE" for i in range(1, 6)
    ]


def test_repeated_prominent_summaries_are_not_running_headers():
    pages = [(i, f"Chapter {i} Unique\nSummary\nBody") for i in range(1, 6)]
    visual = {i: [f"Chapter {i} Unique", "Summary"] for i in range(1, 6)}
    headings = app.headings_from_pages(pages, set(), visual=visual)
    assert len([h for h in headings if h["title"] == "Summary"]) == 5


def test_json_is_valid_under_non_utf8_stdout(tmp_path):
    import json
    import os

    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    env = dict(os.environ, PYTHONIOENCODING="ascii")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--json", "--analyze"],
        capture_output=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["headings"][0]["title"] == "第1章 引言"
    assert result.stdout.isascii()


def test_fullwidth_and_spaceless_chinese_section_numbers():
    assert app.match_heading("４．３角") == {"type": "section", "title": "4.3 角"}
    assert app.match_heading("（ 一 ）基本概念", ocr_mode=True)["type"] == "section"


def test_exam_header_description_does_not_hide_navigation():
    pages = [(1, "2025 年全国统一考试\n一 、 选 择 题 : 本题共8题，共40分。")]
    headings = app.headings_from_pages(pages, {1}, pdf_type="exam")
    assert [h["title"] for h in headings] == ["2025 年全国统一考试", "一、选择题"]


def test_numbered_subsection_keeps_parent_across_sidebar():
    headings = [
        {"type": "chapter", "title": "Chapter 1 Intro", "page": 1},
        {"type": "section", "title": "1.1 Background", "page": 2},
        {"type": "section", "title": "Sidebar", "page": 3},
        {"type": "subsection", "title": "1.1.1 History", "page": 4},
    ]
    assert app.build_tree_from_headings(headings)[-1][-1] == 1


def test_printed_chinese_contents_does_not_create_false_destinations():
    pages = [(1, "目 录\n1.1 数学 5\n1.2 概率 9"), (5, "1.1 数学"), (9, "1.2 概率")]
    headings = app.headings_from_pages(pages, {1, 5, 9}, visual={})
    assert [h["page"] for h in headings] == [5, 9]


def test_version_does_not_require_a_pdf():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0 and app.VERSION in result.stdout


def test_compressed_object_containers_can_be_reserialized(tmp_path):
    source, output = tmp_path / "compressed.pdf", tmp_path / "out.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 80), "Chapter 1 Introduction", fontsize=24)
        page.insert_link(
            {
                "kind": fitz.LINK_URI,
                "from": fitz.Rect(60, 60, 180, 90),
                "uri": "https://example.com",
            }
        )
        doc.set_toc([[1, "Old title", 1]])
        doc.save(source, use_objstms=1)
    assert app.add_bookmarks(source, [(1, "New title", -1)], output, "full") == 1
    assert app.verify_content(source, output, render=True)


def test_numeric_table_does_not_turn_a_heading_page_into_contents():
    text = "7.9 Exercises\n" + "\n".join(
        f"{i}.0 1.41421356237 0.0" for i in range(1, 10)
    )
    headings = app.headings_from_pages(
        [(1, text)], set(), visual={1: ["7.9 Exercises"]}
    )
    assert [h["title"] for h in headings] == ["7.9 Exercises"]
