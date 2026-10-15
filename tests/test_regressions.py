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
        app.add_bookmarks(source, [(1, "Title", -1)], output, overwrite=True)
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
        (("--json", "--analyze", "--overwrite"), True),
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
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            "--json",
            "--analyze",
            "--overwrite",
        ],
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


def test_output_and_edited_toc_are_not_overwritten(tmp_path):
    import json

    source = tmp_path / "book.pdf"
    source.write_bytes(
        (Path(__file__).parent / "fixtures" / "single_page.pdf").read_bytes()
    )
    output = tmp_path / "out.pdf"
    output.write_bytes(b"existing PDF")
    result = run(source, "--json", "-o", output)
    assert result.returncode == 1
    assert "--overwrite" in json.loads(result.stdout)["error"]
    assert output.read_bytes() == b"existing PDF"
    assert run(source, "-o", output, "--overwrite").returncode == 0
    toc = source.with_name("book_suggested_toc.txt")
    toc.write_text("My edited chapter\t1\n")
    assert run(source, "--analyze").returncode == 1
    assert toc.read_text() == "My edited chapter\t1\n"
    assert run(source, "--analyze", "--overwrite").returncode == 0


def test_publish_exclusive_handles_racing_writer(tmp_path):
    temporary, output = tmp_path / "pending", tmp_path / "out"
    temporary.write_bytes(b"new")
    output.write_bytes(b"racing writer")
    with pytest.raises(FileExistsError):
        app.publish_file(temporary, output)
    assert output.read_bytes() == b"racing writer"
    assert temporary.read_bytes() == b"new"


def test_ocr_detection_with_long_watermark_and_inline_image(tmp_path):
    import io

    from PIL import Image

    stream = io.BytesIO()
    Image.new("RGB", (100, 150), "white").save(stream, format="PNG")
    with fitz.open() as doc:
        scan = doc.new_page()
        scan.insert_image(scan.rect, stream=stream.getvalue())
        scan.insert_text((40, 30), "Watermark and copyright text " * 3, fontsize=7)
        assert len(scan.get_text()) > 40
        assert app.page_needs_ocr(scan)
        native = doc.new_page()
        native.insert_image(fitz.Rect(20, 20, 60, 60), stream=stream.getvalue())
        native.insert_textbox(
            fitz.Rect(50, 100, 550, 700), "Normal native text. " * 150
        )
        assert not app.page_needs_ocr(native)

        scan = doc[0]

        class InlinePage:
            rect = scan.rect

            def get_text(self, mode):
                return scan.get_text(mode)

            def get_image_info(self):
                return [{"bbox": tuple(self.rect)}]

            def get_images(self):
                return []

        assert app.page_needs_ocr(InlinePage())


@pytest.mark.requires_tesseract
def test_scanned_result_requires_review(tmp_path):
    import json

    source = Path(__file__).parent / "fixtures" / "scanned.pdf"
    result = run(source, "--lang", "eng", "--json", "-o", tmp_path / "out.pdf")
    data = json.loads(result.stdout)
    assert result.returncode == 0, data
    assert data["review_required"] is True
    assert data["quality"] == "unverified"
    assert data["partial"] is False
    assert any("OCR headings" in warning for warning in data["warnings"])


def test_printed_toc_requires_consistent_independent_body_anchors():
    pages = [(n, "") for n in range(1, 31)]
    titles = [
        "1.1 正数和负数",
        "1.2 有理数加法",
        "1.3 有理数减法",
        "1.4 有理数乘法",
        "1.5 有理数除法",
    ]
    pages[1] = (
        2,
        "\n".join(f"[TOC]\t{title}\t{i + 1}" for i, title in enumerate(titles)),
    )
    assert app.align_printed_toc(pages) == []
    for i, title in enumerate(titles[:3]):
        pages[i + 5] = (i + 6, title)
    aligned = app.align_printed_toc(pages)
    assert [(h["title"], h["page"]) for h in aligned] == [
        (title, i + 6) for i, title in enumerate(titles)
    ]
    # Conflicting printed pagination must not create a guessed offset.
    pages[1] = (2, pages[1][1].replace("\t1\n", "\t12\n").replace("\t2\n", "\t13\n"))
    assert app.align_printed_toc(pages) == []


def test_printed_toc_preserves_titles_when_body_ocr_is_ambiguous():
    pages = [(n, "") for n in range(1, 31)]
    titles = [
        "1.1 正数和负数",
        "1.2 有理数加法",
        "1.3 有理数减法",
        "1.4 有理数乘法",
        "1.5 和四边形性质",
    ]
    pages[1] = (
        2,
        "\n".join(f"[TOC]\t{title}\t{i + 1}" for i, title in enumerate(titles)),
    )
    for i, title in enumerate(titles[:3]):
        pages[i + 5] = (i + 6, title)
    pages[9] = (10, "四边形性质")
    aligned = app.align_printed_toc(pages)
    assert aligned[-1]["title"] == "1.5 和四边形性质"
    assert "body_confirmed" not in aligned[-1]


def test_analysis_output_path_and_protection(tmp_path):
    import json

    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    output = tmp_path / "review.txt"
    result = run(source, "--analyze", "--json", "-o", output)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["toc"] == str(output)
    assert output.read_text(encoding="utf-8") == "第1章 引言\t1\n"
    output.write_text("edited by user")
    assert run(source, "--analyze", "-o", output).returncode == 1
    assert output.read_text() == "edited by user"


def test_printed_toc_folios_still_require_a_matching_body_title():
    pages = [(n, f"[FOLIO]\t{n - 4}" if n >= 5 else "") for n in range(1, 31)]
    titles = [
        "1.1 正数和负数",
        "1.2 有理数加法",
        "1.3 有理数减法",
        "1.4 有理数乘法",
        "1.5 有理数除法",
    ]
    pages[1] = (
        2,
        "\n".join(f"[TOC]\t{title}\t{i + 1}" for i, title in enumerate(titles)),
    )
    assert app.align_printed_toc(pages) == []
    pages[5] = (6, titles[1] + "\n[FOLIO]\t2")
    assert [h["page"] for h in app.align_printed_toc(pages)] == [5, 6, 7, 8, 9]
    pages[5] = (6, titles[1] + "\n[FOLIO]\t99")
    for i in range(6, 26):
        pages[i] = (i + 1, f"[FOLIO]\t{i + 1}")
    assert app.align_printed_toc(pages) == []


def test_outline_sidebar_and_destinations_preserve_page_content(tmp_path):
    source = Path(__file__).parent / "fixtures" / "chinese_text.pdf"
    output = tmp_path / "reader.pdf"
    tree = [(1, "第一章", -1), (2, "第一节", 0), (3, "第二章", -1)]
    app.add_bookmarks(source, tree, output, "full")
    with fitz.open(output) as doc:
        assert doc.pagemode == "UseOutlines"
        assert doc.get_toc() == [[1, "第一章", 1], [2, "第一节", 2], [1, "第二章", 3]]
        for entry in doc.get_toc(simple=False):
            assert entry[3]["kind"] == fitz.LINK_GOTO
            assert entry[3]["page"] == entry[2] - 1
    assert app.verify_content(source, output, render=True)


def test_json_unicode_file_paths_under_ascii_terminal(tmp_path):
    import json
    import os

    source = tmp_path / "中文教材📖.pdf"
    source.write_bytes(
        (Path(__file__).parent / "fixtures" / "single_page.pdf").read_bytes()
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--json", "--analyze"],
        capture_output=True,
        env=dict(os.environ, PYTHONIOENCODING="ascii"),
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True and Path(data["toc"]).is_file()


def test_ocr_spacing_variants_do_not_turn_running_footers_into_chapters():
    pages = [(1, "第一章 有理数\n正文\n第一章 有理数 1")]
    for n in range(2, 6):
        footer = "第 一 章 有 理 数" if n % 2 else "第一章 有理数"
        pages.append((n, f"正文\n{footer} {n}"))
    headings = app.headings_from_pages(
        pages, set(range(1, 6)), visual={1: ["第一章 有理数"]}
    )
    assert [(h["title"], h["page"]) for h in headings] == [("第一章有理数", 1)]


def test_native_auto_outline_always_requires_review(tmp_path):
    import json

    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    result = run(source, "--json", "-o", tmp_path / "out.pdf")
    assert result.returncode == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["quality"] == "unverified" and data["review_required"] is True
    assert data["warnings"] == [] and data["partial"] is False


def test_analysis_creates_nested_output_directory(tmp_path):
    source = Path(__file__).parent / "fixtures" / "single_page.pdf"
    output = tmp_path / "nested" / "review" / "toc.txt"
    result = run(source, "--analyze", "-o", output)
    assert result.returncode == 0, result.stdout
    assert output.read_text(encoding="utf-8") == "第1章 引言\t1\n"


@pytest.mark.parametrize("signature_marker", ["flags", "byte_range", "field_value"])
def test_signature_markers_refused_without_touching_files(tmp_path, signature_marker):
    source, output = tmp_path / "signed.pdf", tmp_path / "out.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((60, 80), "Chapter 1 Example", fontsize=24)
        xref = doc.get_new_xref()
        if signature_marker == "flags":
            doc.update_object(xref, "<< /SigFlags 3 >>")
            doc.xref_set_key(doc.pdf_catalog(), "AcroForm", f"{xref} 0 R")
        elif signature_marker == "byte_range":
            doc.update_object(
                xref, "<< /Type /Sig /ByteRange [0 10 20 30] /Contents <0102> >>"
            )
            doc.xref_set_key(doc.pdf_catalog(), "Perms", f"<< /DocMDP {xref} 0 R >>")
        else:
            doc.update_object(
                xref, "<< /FT /Sig /V << /Type /Sig /Contents <0102> >> >>"
            )
            doc.xref_set_key(
                doc.pdf_catalog(), "AcroForm", f"<< /Fields [{xref} 0 R] >>"
            )
        doc.save(source)
    original = source.read_bytes()
    output.write_bytes(b"existing output")
    with pytest.raises(ValueError, match="Digitally signed PDF"):
        app.add_bookmarks(source, [(1, "Example", -1)], output, overwrite=True)
    result = run(source, "--analyze", "-o", tmp_path / "toc.txt", "--json")
    assert result.returncode == 1 and "Digitally signed PDF" in result.stdout
    assert source.read_bytes() == original and output.read_bytes() == b"existing output"
    assert not (tmp_path / "toc.txt").exists()


def test_marginal_chapter_does_not_hide_body_chapter(tmp_path):
    source = tmp_path / "running-header.pdf"
    with fitz.open() as doc:
        for number in range(3):
            page = doc.new_page()
            page.insert_text((60, 30), "Chapter 1 Navigation", fontsize=14)
            if number == 0:
                page.insert_text((60, 150), "Chapter 1 Navigation", fontsize=32)
            for i in range(8):
                page.insert_text(
                    (60, 230 + 20 * i),
                    "Ordinary body text for the reader.",
                    fontsize=12,
                )
        doc.save(source)
    pages, scanned, visual = app.read_pages(source)
    headings = app.headings_from_pages(pages, scanned, visual=visual)
    assert [(h["page"], h["title"]) for h in headings] == [(1, "Chapter 1 Navigation")]


def test_native_chapter_survives_conflicting_ocr(tmp_path, monkeypatch):
    source = tmp_path / "mixed.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 150), "Chapter 1 Navigation", fontsize=32)
        page.insert_text((60, 230), "Ordinary body text.", fontsize=12)
        doc.save(source)

    class Pool:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def map(self, *args):
            return [(1, "Chapter 9 Wrong OCR", ["Chapter 9 Wrong OCR"])]

    monkeypatch.setattr(app, "ProcessPoolExecutor", Pool)
    pages, scanned, visual = app.read_pages(source, lang="eng", force_ocr=True)
    headings = app.headings_from_pages(pages, scanned, visual=visual)
    assert [(h["page"], h["title"]) for h in headings] == [(1, "Chapter 1 Navigation")]


def test_appendix_sections_and_subsections_keep_their_parent():
    titles = [
        "Chapter 1 Body",
        "1.1 Section",
        "Appendix A Tools",
        "A.1 Installation",
        "Sidebar",
        "A.1.1 Windows",
        "A.2 Usage",
        "Appendix B Debugging",
        "B.1 Errors",
        "Preface",
        "Chapter 2 Next",
    ]
    headings = []
    for page, title in enumerate(titles, 1):
        entry = app.match_heading(title) or {
            "type": "section" if title == "Sidebar" else "chapter",
            "title": title,
        }
        headings.append(dict(entry, page=page))
    tree = app.build_tree_from_headings(headings)
    assert tree[3][2] == 2 and tree[5][2] == 3 and tree[6][2] == 2
    assert tree[8][2] == 7 and tree[9][2] == -1 and tree[10][2] == -1
    assert app.match_heading("A. Tools")["type"] == "chapter"


def test_cryptographically_signed_fixture_is_preserved(tmp_path):
    import base64
    import hashlib

    fixture = Path(__file__).parent / "fixtures" / "signed_pdf.b64"
    data = base64.decodebytes(fixture.read_bytes())
    assert (
        hashlib.sha256(data).hexdigest()
        == "5eeedec87a4e3fc098efdbfb3a8cdc03aba1168f2632279d424b4dfe37e99f84"
    )
    source = tmp_path / "signed.pdf"
    source.write_bytes(data)
    output = tmp_path / "out.pdf"
    result = run(source, "--json", "-o", output)
    assert result.returncode == 1 and "Digitally signed PDF" in result.stdout
    assert source.read_bytes() == data and not output.exists()


def test_unused_free_xref_does_not_trigger_signature_failure(tmp_path):
    import re

    source, output = tmp_path / "free.pdf", tmp_path / "out.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((60, 80), "Chapter 1 Example", fontsize=24)
        unused = doc.get_new_xref()
        doc.update_object(unused, "<< /Unused true >>")
        data = doc.tobytes()
    match = re.search(rb"\nxref\n0 (\d+)\n", data)
    assert match and unused < int(match[1])
    start = match.end() + 20 * unused
    data = data[:start] + b"0000000000 00000 f \n" + data[start + 20 :]
    source.write_bytes(data)
    assert app.add_bookmarks(source, [(1, "Example", -1)], output, "full") == 1
    assert source.read_bytes() == data and app.verify_content(
        source, output, render=True
    )
    import json

    result = run(source, "--json", "--verify", "full", "-o", tmp_path / "json.pdf")
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["ok"] is True


def test_vertical_native_title_ignores_other_column_and_side_margin(tmp_path):
    source = tmp_path / "vertical.pdf"
    with fitz.open() as doc:
        for number in range(3):
            page = doc.new_page()
            page.insert_text((15, 200), "Repeated side margin", fontsize=12, rotate=90)
            if number == 0:
                page.insert_text((70, 230), "Propagation", fontsize=20)
                for offset, char in enumerate("声现象"):
                    page.insert_text(
                        (270, 100 + offset * 30), char, fontsize=28, fontname="china-s"
                    )
                    page.insert_text(
                        (340, 100 + offset * 30),
                        "Preview of a later section",
                        fontsize=12,
                    )
            for offset in range(6):
                page.insert_text(
                    (70, 300 + offset * 20),
                    "Ordinary body text for the reader.",
                    fontsize=12,
                )
        doc.save(source)
    pages, scanned, visual = app.read_pages(source)
    headings = app.headings_from_pages(pages, scanned, visual=visual)
    assert [(h["page"], h["title"], h["type"]) for h in headings] == [
        (1, "声现象", "chapter"),
        (1, "Propagation", "section"),
    ]
    assert app.build_tree_from_headings(headings)[1][2] == 0
    assert all("Repeated side margin" not in text for _, text in pages)


def test_numbered_ocr_header_cannot_move_native_chapter():
    headings = [
        {
            "page": 86,
            "type": "chapter",
            "title": "光的折射透镜",
            "source": "native_vertical",
        },
        {"page": 90, "type": "chapter", "title": "第四章光的折射 ”透镜"},
        {"page": 108, "type": "chapter", "title": "第五章 物体的运动"},
        {"page": 110, "type": "chapter", "title": "Summary"},
        {"page": 118, "type": "chapter", "title": "Summary"},
    ]
    assert [h["page"] for h in app.filter_headings(headings)] == [86, 108, 110, 118]


def test_benchmark_precision_counts_duplicate_bookmarks():
    import importlib.util

    path = Path(__file__).parent / "network_smoke.py"
    spec = importlib.util.spec_from_file_location("benchmark_scoring", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.score([(1, "Chapter 1 Intro", 2)], [(1, "Chapter 1 Intro", 2)] * 2)
    assert result["exact_matches"] == 1
    assert result["scored_candidates"] == 2
    assert result["duplicate_candidates"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 1


def test_semantic_units_chapters_sections_and_appendix_reset():
    from headings import build_tree_from_headings, match_heading

    titles = [
        "第一单元 生命",
        "第一章 结构",
        "第一节 细胞",
        "第二节 组织",
        "第二单元 环境",
        "第一章 生态",
        "第一节 循环",
        "附录一 词汇",
    ]
    tree = build_tree_from_headings(
        [dict(match_heading(title), page=i + 1) for i, title in enumerate(titles)]
    )
    assert [row[2] for row in tree] == [-1, 0, 1, 1, -1, 4, 5, -1]


def test_outline_diagnostics_expose_conflicts_and_unconfirmed_pages():
    from headings import diagnose_outline

    headings = [
        dict(type="chapter", title="第1章 基础", page=3),
        dict(type="section", title="2.1 错配", page=4),
        dict(type="section", title="第一节", page=5),
        dict(type="chapter", title="第1章 基础", page=6),
    ]
    diagnostics = diagnose_outline(headings, [(1, "[TOC]\t第1章 基础\t1")])
    assert {d["code"] for d in diagnostics} == {
        "hierarchy_conflict",
        "fragmented_heading",
        "suspected_running_header",
        "unconfirmed_pagination",
    }
    assert all(d["pages"] for d in diagnostics)


def test_native_contents_pairs_left_and_right_folios_without_guessing():
    from headings import native_toc_rows

    lines = []
    for i in range(5):
        y = i * 30
        lines += [
            dict(bbox=(100, y, 250, y + 15), spans=[dict(text=f"第{i + 1}节 标题")]),
            dict(
                bbox=((70 if i % 2 else 270), y, (90 if i % 2 else 290), y + 15),
                spans=[dict(text=str(i + 2))],
            ),
        ]
    assert native_toc_rows(lines) == [
        f"[TOC]\t第{i + 1}节标题\t{i + 2}" for i in range(5)
    ]
    # Two possible folios on one row are ambiguous; do not choose either.
    lines.append(dict(bbox=(300, 0, 320, 15), spans=[dict(text="9")]))
    assert native_toc_rows(lines) == []


def test_contents_page_marker_cannot_create_body_bookmarks():
    from headings import headings_from_pages

    pages = [
        (1, "[CONTENTS]\n第一单元 生命\n第一章 细胞"),
        (2, "第一单元 生命"),
        (3, "第一章 细胞"),
        (4, "第一节 结构"),
    ]
    assert [h["page"] for h in headings_from_pages(pages, set(), "textbook")] == [
        2,
        3,
        4,
    ]


def test_inline_printed_contents_requires_repeated_explicit_separators():
    from headings import native_toc_rows

    def line(text, y):
        return dict(bbox=(50, y, 300, y + 15), spans=[dict(text=text)])

    titles = ["第一章 概述", "第一节 方法", "整理与归纳", "第二章 应用", "附 录"]
    for leading in (False, True):
        lines = [
            line(f"{i + 1}/ {title}" if leading else f"{title} ------ {i + 1}", i * 30)
            for i, title in enumerate(titles)
        ]
        rows = native_toc_rows(lines)
        assert len(rows) == 5
        assert rows[-1] == "[TOC]\t附录\t5"
    assert (
        native_toc_rows(
            [line(f"{title} {i + 1}", i * 30) for i, title in enumerate(titles)]
        )
        == []
    )
    assert (
        native_toc_rows([line(f"练习 ------ {i + 1}", i * 30) for i in range(8)]) == []
    )


def test_confirmed_contents_keeps_unnumbered_children_and_discards_visual_tail():
    from headings import build_tree_from_headings, headings_from_pages

    titles = ["第一章概述", "第一节方法", "整理与归纳", "第二章应用", "附录"]
    pages = [
        (
            1,
            "[CONTENTS]\n"
            + "\n".join(f"[TOC]\t{title}\t{i + 1}" for i, title in enumerate(titles)),
        )
    ]
    pages += [(i + 2, title) for i, title in enumerate(titles)]
    pages.append((7, "活动"))
    visual = {n: text.splitlines() for n, text in pages}
    headings = headings_from_pages(pages, set(), "textbook", visual)
    assert [h["title"] for h in headings] == titles
    tree = build_tree_from_headings(headings)
    assert [parent for _, _, parent in tree] == [-1, 0, 0, -1, -1]


def test_native_spaced_appendix_starts_new_root():
    from headings import build_tree_from_headings, match_heading

    headings = [
        dict(match_heading(title), page=i + 1)
        for i, title in enumerate(["第五章应用", "第一节方法", "附  录"])
    ]
    assert headings[-1]["title"] == "附录"
    assert build_tree_from_headings(headings)[-1][2] == -1


def test_row_scoped_ocr_alternatives_require_exact_body_corroboration():
    titles = [
        "1.1 初始错字",
        "1.2 图像处理",
        "1.3 数据结构",
        "1.4 程序设计",
        "1.5 网络协议",
    ]
    pages = [(n, "") for n in range(1, 12)]
    pages[0] = (
        1,
        "\n".join(f"[TOC]\t{t}\t{i + 1}" for i, t in enumerate(titles))
        + "\n[TOC_ALT]\t1.1 初始错字\t1.1 正确标题\t1",
    )
    for i, title in enumerate(titles):
        pages[i + 3] = (i + 4, "1.1 正确标题" if i == 0 else title)
    aligned = app.align_printed_toc(pages)
    assert aligned[0]["title"] == "1.1 正确标题"
    assert aligned[0]["page"] == 4
    # A candidate from a different contents row sharing the folio is not evidence.
    pages[0] = (
        1,
        pages[0][1].replace("[TOC_ALT]\t1.1 初始错字", "[TOC_ALT]\t1.9 其他条目"),
    )
    assert app.align_printed_toc(pages)[0]["title"] == titles[0]
    pages[3] = (4, "")
    assert app.align_printed_toc(pages)[0]["title"] == titles[0]


def test_extended_body_titles_remain_leaves_under_printed_outline():
    from headings import build_tree_from_headings, headings_from_pages

    titles = ["第一章概述", "第一节方法", "第二章应用", "第一节实例", "附录"]
    pages = [
        (
            1,
            "[CONTENTS]\n"
            + "\n".join(f"[TOC]\t{title}\t{i + 1}" for i, title in enumerate(titles)),
        )
    ]
    pages += [
        (i + 2, title + ("\n研究活动" if i == 1 else ""))
        for i, title in enumerate(titles)
    ]
    visual = {n: text.splitlines() for n, text in pages}
    normal = headings_from_pages(pages, set(), "textbook", visual)
    expanded = headings_from_pages(pages, set(), "textbook", visual, extended=True)
    assert [h["title"] for h in normal] == titles
    assert [h["title"] for h in expanded] == titles[:2] + ["研究活动"] + titles[2:]
    tree = build_tree_from_headings(expanded)
    assert [parent for _, _, parent in tree] == [-1, 0, 1, -1, 3, -1]


def test_small_ocr_glyphs_do_not_crash_contents_analysis(monkeypatch):
    import pytesseract
    from ocr import read_semantic_toc
    from PIL import Image

    data = {key: [] for key in ["text", "left", "top", "width", "height", "conf"]}
    for i in range(5):
        for values in [
            (f"第{i + 1}章标题", 100, 150 + i * 40, 100, 9, 90),
            (str(i + 1), 900, 150 + i * 40, 10, 9, 90),
        ]:
            for key, value in zip(data, values, strict=True):
                data[key].append(value)
    monkeypatch.setattr(
        pytesseract, "image_to_data", lambda *args, **kwargs: {key: [] for key in data}
    )
    result = read_semantic_toc(
        Image.new("RGB", (1000, 1000), "white"), data, "chi_sim+eng", 100
    )
    assert sum(line.startswith("[TOC]\t") for line in result) == 5


def test_body_corroboration_allows_missing_marker_but_not_a_different_marker():
    titles = [
        "1.1 初始错字",
        "1.2 图像处理",
        "1.3 数据结构",
        "1.4 程序设计",
        "1.5 网络协议",
    ]
    pages = [(n, "") for n in range(1, 12)]
    pages[0] = (
        1,
        "\n".join(f"[TOC]\t{t}\t{i + 1}" for i, t in enumerate(titles))
        + "\n[TOC_ALT]\t1.1 初始错字\t1.1 正确标题\t1",
    )
    for i, title in enumerate(titles):
        pages[i + 3] = (i + 4, "正确标题" if i == 0 else title)
    assert app.align_printed_toc(pages)[0]["title"] == "1.1 正确标题"
    pages[0] = (1, pages[0][1].replace("\t1.1 正确标题\t", "\t1.9 正确标题\t"))
    assert app.align_printed_toc(pages)[0]["title"] == titles[0]
