#!/usr/bin/env python3
# All examples are synthetic placeholders, not excerpts from user documents.
import os, sys, subprocess, time, pytest
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / 'scripts'
FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'
OUTPUT_DIR = Path(__file__).resolve().parent / 'output'
SCRIPT = SCRIPTS_DIR / 'add_bookmarks.py'
SCANNED_PDF = FIXTURES_DIR / 'scanned.pdf'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
def run_script(args, expect_success=True):
    cmd = [sys.executable, str(SCRIPT)] + args
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    elapsed = time.time() - start
    if expect_success and result.returncode != 0:
        print(f'STDOUT:\n{result.stdout}')
        print(f'STDERR:\n{result.stderr}')
    return result.returncode, result.stdout, result.stderr, elapsed

def verify_bookmarks(output_path, expected_count=None, expected_structure=None):
    import fitz
    assert Path(output_path).exists(), f'Output not found: {output_path}'
    doc = fitz.open(output_path)
    toc = doc.get_toc()
    if expected_count is not None:
        assert len(toc) == expected_count, f'Expected {expected_count}, got {len(toc)}'
    if expected_structure is not None:
        for i, (level, title, page) in enumerate(expected_structure):
            assert toc[i][0] == level, f'Entry {i}: level mismatch'
            assert toc[i][1] == title, f'Entry {i}: title mismatch'
            assert toc[i][2] == page, f'Entry {i}: page mismatch'
    doc.close()
    return toc

def verify_content_integrity(input_path, output_path):
    import fitz
    orig = fitz.open(input_path)
    new = fitz.open(output_path)
    assert len(orig) == len(new), f'Page count mismatch'
    check_pages = [0]
    if len(orig) > 1: check_pages.append(len(orig) // 2)
    if len(orig) > 2: check_pages.append(len(orig) - 1)
    for i in check_pages:
        assert orig[i].get_text() == new[i].get_text(), f'Page {i+1} differs'
    orig.close(); new.close()

@pytest.fixture(autouse=True)
def cleanup_output():
    for f in OUTPUT_DIR.glob('*.pdf'):
        try:
            f.unlink()
        except (OSError, PermissionError):
            pass
    for d in OUTPUT_DIR.glob('**/*'):
        if d.is_dir() and d != OUTPUT_DIR:
            for f in d.glob('*'):
                try:
                    f.unlink()
                except (OSError, PermissionError):
                    pass
            try:
                d.rmdir()
            except OSError:
                pass
    yield

class TestChineseTextPDF:
    def test_auto_detect_text_based(self):
        output = OUTPUT_DIR / 'tc01_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'), '-o', str(output),
        ])
        assert rc == 0, f'Failed: {stderr}'
        assert 'Text-based' in stdout
        assert 'Found 7 headings' in stdout
        assert 'Added 7 bookmarks' in stdout

    def test_bookmark_structure(self):
        output = OUTPUT_DIR / 'tc01_out.pdf'
        run_script([str(FIXTURES_DIR / 'chinese_text.pdf'), '-o', str(output)])
        expected = [
            (1, '第1章 概述', 1),
            (2, '1.1 研究背景', 2),
            (3, '1.1.1 历史回顾', 3),
            (2, '1.2 研究目标', 4),
            (1, '第2章 方法', 5),
            (2, '2.1 实验设计', 6),
            (3, '2.1.1 数据采集', 7),
        ]
        verify_bookmarks(output, expected_count=7, expected_structure=expected)

    def test_content_integrity(self):
        output = OUTPUT_DIR / 'tc01_out.pdf'
        run_script([str(FIXTURES_DIR / 'chinese_text.pdf'), '-o', str(output)])
        verify_content_integrity(FIXTURES_DIR / 'chinese_text.pdf', output)

class TestEnglishTextPDF:
    def test_auto_detect_text_based(self):
        output = OUTPUT_DIR / 'tc02_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'english_text.pdf'), '-o', str(output),
        ])
        assert rc == 0
        assert 'Text-based' in stdout
        assert 'Found 6 headings' in stdout

    def test_bookmark_structure(self):
        output = OUTPUT_DIR / 'tc02_out.pdf'
        run_script([str(FIXTURES_DIR / 'english_text.pdf'), '-o', str(output)])
        expected = [
            (1, '1. Introduction', 1),
            (2, '1.1 Background', 2),
            (3, '1.1.1 Historical Context', 3),
            (1, 'Chapter 2 Methods', 4),
            (2, '2.1 Experimental Design', 5),
            (3, '2.1.1 Data Collection', 6),
        ]
        verify_bookmarks(output, expected_count=6, expected_structure=expected)

    def test_content_integrity(self):
        output = OUTPUT_DIR / 'tc02_out.pdf'
        run_script([str(FIXTURES_DIR / 'english_text.pdf'), '-o', str(output)])
        verify_content_integrity(FIXTURES_DIR / 'english_text.pdf', output)

class TestTOCFileMode:
    def test_toc_chinese(self):
        output = OUTPUT_DIR / 'tc04_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--toc', str(FIXTURES_DIR / 'toc.txt'),
            '-o', str(output),
        ])
        assert rc == 0
        assert '7 TOC entries' in stdout
        expected = [
            (1, '第1章 概述', 1),
            (2, '1.1 研究背景', 2),
            (3, '1.1.1 历史回顾', 3),
            (2, '1.2 研究目标', 4),
            (1, '第2章 方法', 5),
            (2, '2.1 实验设计', 6),
            (3, '2.1.1 数据采集', 7),
        ]
        verify_bookmarks(output, expected_count=7, expected_structure=expected)

    def test_toc_english(self):
        output = OUTPUT_DIR / 'tc04_en_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'english_text.pdf'),
            '--toc', str(FIXTURES_DIR / 'toc_en.txt'),
            '-o', str(output),
        ])
        assert rc == 0
        assert '6 TOC entries' in stdout
        toc = verify_bookmarks(output, expected_count=6)
        assert toc[0][1] == '1. Introduction'

class TestContentIntegrity:
    def test_chinese(self):
        output = OUTPUT_DIR / 'tc10_chinese.pdf'
        run_script([str(FIXTURES_DIR / 'chinese_text.pdf'), '-o', str(output)])
        verify_content_integrity(FIXTURES_DIR / 'chinese_text.pdf', output)

    def test_english(self):
        output = OUTPUT_DIR / 'tc10_english.pdf'
        run_script([str(FIXTURES_DIR / 'english_text.pdf'), '-o', str(output)])
        verify_content_integrity(FIXTURES_DIR / 'english_text.pdf', output)

    def test_large(self):
        output = OUTPUT_DIR / 'tc10_large.pdf'
        run_script([str(FIXTURES_DIR / 'large.pdf'), '-o', str(output)])
        import fitz
        orig = fitz.open(FIXTURES_DIR / 'large.pdf')
        new = fitz.open(output)
        assert len(orig) == len(new) == 100
        orig.close(); new.close()

class TestScannedPDF:
    @pytest.mark.slow
    @pytest.mark.requires_tesseract
    def test_ocr_detection_and_bookmarks(self):
        if not SCANNED_PDF.exists():
            pytest.skip(f'Scanned PDF not found: {SCANNED_PDF}')
        output = OUTPUT_DIR / 'tc03_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(SCANNED_PDF), '-o', str(output),
        ], expect_success=True)
        assert rc == 0, stderr + stdout
        toc = verify_bookmarks(output)
        assert [entry[1] for entry in toc] == ['Chapter 1 Introduction', 'Chapter 2 Methods']
        assert [entry[2] for entry in toc] == [1, 2]
        verify_content_integrity(SCANNED_PDF, output)

class TestSinglePagePDF:
    def test_single_page(self):
        output = OUTPUT_DIR / 'tc05_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'single_page.pdf'), '-o', str(output),
        ])
        assert rc == 0
        verify_bookmarks(output, expected_count=1,
                         expected_structure=[(1, '第1章 引言', 1)])

class TestNoHeadingsPDF:
    def test_no_headings_exits_error(self):
        output = OUTPUT_DIR / 'tc06_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'no_headings.pdf'), '-o', str(output),
        ], expect_success=False)
        assert rc == 1
        assert 'No headings detected' in stdout

class TestImageOnlyPDF:
    def test_image_only_no_crash(self):
        output = OUTPUT_DIR / 'tc07_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'images_only.pdf'), '-o', str(output),
        ], expect_success=False)
        assert rc in (0, 1)
        assert 'Traceback' not in stderr

class TestForceOCR:
    @pytest.mark.requires_tesseract
    def test_force_ocr_on_text_pdf(self):
        output = OUTPUT_DIR / 'tc09_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--force-ocr', '-o', str(output),
        ], expect_success=True)
        assert rc == 0, stdout + stderr
        if rc == 0:
            assert 'OCR' in stdout.upper() or 'Image-based' in stdout
            toc = verify_bookmarks(output)
            assert len(toc) > 0

class TestTOCOffset:
    def test_toc_offset(self):
        output = OUTPUT_DIR / 'tc12_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--toc', str(FIXTURES_DIR / 'toc_offset.txt'),
            '--offset', '-2', '-o', str(output),
        ])
        assert rc == 0
        expected = [
            (1, '第1章 概述', 1),
            (2, '1.1 研究背景', 2),
            (1, '第2章 方法', 5),
        ]
        verify_bookmarks(output, expected_count=3, expected_structure=expected)

class TestLargePDF:
    def test_large_pdf_text_mode(self):
        output = OUTPUT_DIR / 'tc08_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'large.pdf'), '-o', str(output),
        ])
        assert rc == 0
        assert elapsed < 30, f'Text mode took {elapsed:.1f}s'
        import fitz
        doc = fitz.open(output)
        assert len(doc) == 100
        toc = doc.get_toc()
        assert len(toc) == 10, f'Expected 10, got {len(toc)}'
        doc.close()

class TestCustomOutputPath:
    def test_custom_output_path(self):
        custom = OUTPUT_DIR / 'custom' / 'path' / 'out.pdf'
        run_script([str(FIXTURES_DIR / 'single_page.pdf'), '-o', str(custom)])
        assert custom.exists()
        verify_bookmarks(custom, expected_count=1)

class TestOCRLanguageOption:
    @pytest.mark.requires_tesseract
    def test_lang_option(self):
        output = OUTPUT_DIR / 'tc13_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--force-ocr', '--lang', 'chi_sim', '-o', str(output),
        ], expect_success=True)
        assert rc == 0, stdout + stderr
        if rc == 0:
            toc = verify_bookmarks(output)
            assert len(toc) > 0



class TestV2OCRNoiseCleaning:
    def test_match_heading_clean(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import match_heading
        assert match_heading('第1章 概述') is not None
        assert match_heading('1.1.1 历史回顾') is not None
        assert match_heading('1. Introduction') is not None
        assert match_heading('Chapter 2 Methods') is not None
        assert match_heading('random text') is None

    def test_match_heading_noisy(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import match_heading
        assert match_heading('第 1 章 概述') is not None
        assert match_heading('1 .1 研究背景') is not None
        assert match_heading('1.1.1 历史回顾') is not None

class TestV3PDFTypeDetection:
    def test_detect_textbook(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import read_pages, headings_from_pages
        pages, scanned, visual = read_pages(str(FIXTURES_DIR / "chinese_text.pdf"))
        assert not scanned
        assert len(headings_from_pages(pages, scanned, "textbook", visual)) == 7

    def test_detect_exam_patterns_in_text(self):
        """Verify exam heading patterns match correctly."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import match_heading
        assert match_heading('2000年试题 示例甲') is not None
        assert match_heading('2001年试题 示例乙') is not None
        assert match_heading('第1讲 示例内容') is not None
        assert match_heading('2002年试题 示例丙') is not None

    def test_detect_outline_markers(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import match_heading
        assert match_heading('一、示例标题') is not None
        assert match_heading('（一）基本概念') is not None

    def test_exam_heading_filters_correctly(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import match_heading, filter_headings
        headings = [
            {"type": "chapter", "title": "2000年试题 示例甲", "page": 6},
            {"type": "chapter", "title": "2003年试题 示例丁", "page": 24},
        ]
        filtered = filter_headings(headings, total_pages=24)
        assert len(filtered) == 2

class TestV3AnalyzeMode:
    def test_analyze_suggested_toc_file(self):
        output = OUTPUT_DIR / 'v3_analyze_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--analyze',
        ], expect_success=True)
        assert rc == 0
        suggested = FIXTURES_DIR / '..' / '..' / 'chinese_text_suggested_toc.txt'
        # Check output mentions candidates
        assert 'Suggested TOC' in stdout

    def test_exam_headings_via_analyze(self):
        """Test that exam PDF headings can be detected via --analyze."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from add_bookmarks import headings_from_pages
        # Simulate OCR output for exam PDF-style pages
        all_text = [
            (1, "第1讲 示例内容\n占位说明文字\n示例页脚"),
            (2, "2004年试题 示例戊\n这是一段用于测试的占位正文。\n示例页脚"),
            (3, "2005年试题 示例己\n这是另一段用于测试的占位正文。\n示例页脚"),
        ]
        candidates = headings_from_pages(all_text, set())
        assert len(candidates) == 3, f'Expected 3, got {len(candidates)}'
        assert '2004' in candidates[1]['title']
        assert '2005' in candidates[2]['title']

class TestV3GenerateTOC:
    def test_generate_toc_on_text_pdf(self):
        output = OUTPUT_DIR / 'v3_gen_out.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--generate-toc', '-o', str(output),
        ], expect_success=True)
        assert rc == 0
        assert output.exists()
        import fitz
        doc = fitz.open(output)
        toc = doc.get_toc()
        assert len(toc) > 0, 'Expected at least 1 bookmark'
        doc.close()

class TestV2EdgeCases:
    def test_empty_toc_file(self):
        empty = FIXTURES_DIR / 'empty_toc.txt'
        empty.write_text('', encoding='utf-8')
        output = OUTPUT_DIR / 'tc_empty_toc.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--toc', str(empty), '-o', str(output),
        ], expect_success=False)
        assert rc == 1
        assert 'No entries' in stdout

    def test_nonexistent_toc_file(self):
        output = OUTPUT_DIR / 'tc_nonexist.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'chinese_text.pdf'),
            '--toc', str(FIXTURES_DIR / 'nonexistent.txt'),
            '-o', str(output),
        ], expect_success=False)
        assert rc == 1
        assert 'not found' in stdout.lower()

    def test_nonexistent_input_pdf(self):
        output = OUTPUT_DIR / 'tc_nonexist_input.pdf'
        rc, stdout, stderr, elapsed = run_script([
            str(FIXTURES_DIR / 'nonexistent.pdf'),
            '-o', str(output),
        ], expect_success=False)
        assert rc == 1
        assert 'not found' in stdout.lower()

    def test_default_output_name(self):
        import shutil
        cwd = os.getcwd()
        os.chdir(str(OUTPUT_DIR))
        try:
            src = FIXTURES_DIR / 'single_page.pdf'
            dst = OUTPUT_DIR / 'single_page.pdf'
            shutil.copy(src, dst)
            rc, stdout, stderr, elapsed = run_script([str(dst)])
            assert rc == 0
            expected = OUTPUT_DIR / 'single_page_with_bookmarks.pdf'
            assert expected.exists(), f'Default output not found: {expected}'
            verify_bookmarks(expected, expected_count=1)
        finally:
            os.chdir(cwd)
