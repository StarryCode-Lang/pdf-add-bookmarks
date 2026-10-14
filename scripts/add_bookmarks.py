#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path

VERSION = "0.2.0"


def find_tesseract():
    path = shutil.which("tesseract")
    if path:
        return path
    if sys.platform == "win32":
        for c in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]:
            if os.path.exists(c):
                return c
    elif sys.platform == "darwin":
        for c in ["/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]:
            if os.path.exists(c):
                return c
    else:
        for c in ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.exists(c):
                return c
    return None


def ensure_tesseract():
    import pytesseract

    try:
        pytesseract.get_languages()
        return True
    except Exception:
        path = find_tesseract()
        if path:
            pytesseract.pytesseract.tesseract_cmd = path
            try:
                pytesseract.get_languages()
                return True
            except Exception:
                pass
    return False


def clean_ocr_line(line, ocr_mode=False):
    line = unicodedata.normalize("NFKC", line)
    cleaned = re.sub(
        r"^[^\w\u4e00-\u9fff\d\u3000-\u303f\uff00-\uffef()]+", "", line
    ).strip()
    # Normalize spaces in "第 X 章" → "第X章"
    cleaned = re.sub(r"第\s+(\d+)\s+章", r"第\1章", cleaned)
    cleaned = re.sub(r"第\s+([一二三四五六七八九十]+)\s+章", r"第\1章", cleaned)
    # Normalize "X .X" → "X.X"
    cleaned = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", cleaned)
    cleaned = re.sub(r"^(\d+(?:\.\d+){1,2})(?=[A-Za-z\u4e00-\u9fff])", r"\1 ", cleaned)
    cleaned = re.sub(r"^([一二三四五六七八九十]+)\s*、\s*", r"\1、", cleaned)
    cleaned = re.sub(r"^\(\s*([一二三四五六七八九十]+)\s*\)", r"(\1)", cleaned)
    if ocr_mode:
        # Iteratively normalize spaces between Chinese characters (OCR artifact)
        while True:
            new = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", cleaned)
            if new == cleaned:
                break
            cleaned = new
    return cleaned if cleaned else line.strip()


def match_heading(line, ocr_mode=False, pdf_type="auto"):
    result = _match_heading(line, ocr_mode)
    cleaned = clean_ocr_line(line, ocr_mode)
    exam = bool(re.match(r"^(20\d{2}).*(真题|应用题|统考|试题|考试)|^第\d+讲", cleaned))
    outline = bool(
        re.match(
            r"^[一二三四五六七八九十]+、|^[（(][一二三四五六七八九十]+[）)]", cleaned
        )
    )
    if pdf_type == "textbook" and (exam or outline):
        return None
    if pdf_type == "exam" and not (exam or outline):
        return None
    if (
        pdf_type == "slides"
        and result
        and not (outline or re.match(r"^第.*讲|^\d+[.)]\s", cleaned))
    ):
        return None
    if pdf_type in ("auto", "article"):
        if pdf_type == "article" and (
            exam or outline or re.match(r"^(Chapter|Part|第.*章)", cleaned, re.I)
        ):
            return None
        if re.fullmatch(
            r"Abstract|Introduction|Background|Methods|Results|Discussion|Conclusions?|References|摘要|引言|方法|结果|讨论|结论|参考文献",
            cleaned,
            re.I,
        ):
            return {"type": "chapter", "title": cleaned}
    return result


def _match_heading(line, ocr_mode=False):
    line = clean_ocr_line(line, ocr_mode=ocr_mode)
    if not line:
        return None
    if re.match(r"^第[一二三四五六七八九十]+章\s*", line):
        return {"type": "chapter", "title": line}
    m = re.match(r"^第(\d+)章\s*(.+)", line)
    if m:
        return {"type": "chapter", "title": line}
    if re.match(
        r"^(?:Chapter|Part)\s+(?:\d+|[IVXLCDM]+)\b|^Appendix\s+(?:\d+|[A-Z])\b",
        line,
        re.IGNORECASE,
    ):
        return {"type": "chapter", "title": line}
    m = re.match(r"^(\d+\.\d+\.\d+)\s+(.+)", line)
    if m:
        return {"type": "subsection", "title": line}
    m = re.match(r"^(\d+\.\d+)\s+([A-Za-z\u4e00-\u9fff].{0,80})$", line)
    if m:
        return {"type": "section", "title": line}
    m = re.match(r"^(\d+)\.\s+([A-Z][A-Za-z].{0,60})$", line)
    if m and 1 <= int(m.group(1)) <= 20:
        return {"type": "chapter", "title": line}
    m = re.match(r"^(\d+)\s+([\u4e00-\u9fff][\u4e00-\u9fff\s]{0,15})$", line)
    if m and 1 <= int(m.group(1)) <= 99:
        return {"type": "chapter", "title": line}
    m = re.match(r"^(\d+)\s+([A-Z][A-Za-z\s\-]{2,40})$", line)
    if m and 1 <= int(m.group(1)) <= 99:
        return {"type": "chapter", "title": line}
    if re.match(r"^[A-Z]\.\d+\.?\s+\w+", line):
        return {"type": "subsection", "title": line}
    # Match generic year-prefixed examination headings.
    m = re.match(r"^(20\d{2})\s*年.*(?:真题|应用题|统考|试题|考试)", line)
    if m:
        return {"type": "chapter", "title": line}
    m = re.match(r"^(20\d{2})[年\s]*.*[真应考]题", line)
    if m:
        return {"type": "chapter", "title": line}
    # Lecture patterns: "第X讲"
    if re.match(r"^第\d+讲\s*", line):
        return {"type": "chapter", "title": line}
    # Outline markers: "一、", "（一）", "1." at line start for slides/outlines
    if re.match(r"^[一二三四五六七八九十]+[、]", line):
        return {"type": "section", "title": line}
    if re.match(r"^[（(][一二三四五六七八九十]+[）)]", line):
        return {"type": "section", "title": line}
    return None


def _is_garbage_title(title):
    """Detect OCR garbage titles."""
    if len(title) < 2:
        return True
    # Count non-standard characters (not Chinese, not English letter, not digit, not common punctuation)
    non_standard = sum(
        1 for c in title if not (c.isalnum() or c.isspace() or c in "._()-，、：:;；")
    )
    if len(title) > 0 and non_standard / len(title) > 0.4:
        return True
    return False


def _is_body_text_word(title):
    """Reject common body text words that shouldn't be chapter titles."""
    body_words = {
        "注意",
        "本章",
        "上述",
        "下面",
        "其中",
        "因此",
        "所以",
        "但是",
        "例如",
        "比如",
        "总之",
        "此外",
        "另外",
        "首先",
        "其次",
        "最后",
        "结论",
        "摘要",
    }
    # Normalize spaces first (OCR often inserts spaces between Chinese chars)
    normalized = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", title)
    stripped = re.sub(r"^\d+\s*\.?\s*", "", normalized).strip()
    if stripped in body_words:
        return True
    return False


def _is_introduction_text(title):
    """Reject body text that mentions chapters but isn't a real heading."""
    # Only reject the specific pattern "第X章 : XXX" — not all parentheses (exam years use them)
    if re.match(r"^第[一二三四五六七八九十]+章\s*[:：]\s", title):
        return True
    return False


def filter_headings(headings, total_pages=None):
    """Post-process: remove false positives, garbage, duplicates."""
    if not headings:
        return []
    if total_pages is None:
        total_pages = max(h["page"] for h in headings) if headings else 0
    filtered = []
    seen_titles = set()
    chapter, section = None, None

    for h in sorted(headings, key=lambda h: h["page"]):
        title = h["title"]
        htype = h["type"]
        page = h["page"]

        # Reject garbage
        if _is_garbage_title(title):
            continue

        # Reject body text words for chapters
        if htype == "chapter" and _is_body_text_word(title):
            continue

        # Reject introduction text that mentions chapters
        if htype == "chapter" and _is_introduction_text(title):
            continue

        # Reject overly long chapter titles (likely sentences, not headings)
        if htype == "chapter" and len(title) > 100:
            continue

        # Deduplicate within the parent, preserving legitimate repeated child titles.
        scope = (
            (page,)
            if htype == "chapter"
            else (chapter, section if htype == "subsection" else None)
        )
        key = (htype, title, scope)
        if key in seen_titles:
            continue
        seen_titles.add(key)
        filtered.append(h)
        if htype == "chapter":
            chapter, section = (title, page), None
        elif htype == "section":
            section = (title, page)

    return filtered


def parse_toc_file(toc_path, offset=0):
    with open(toc_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    indent_stack = []
    for number, line in enumerate(lines, 1):
        line = line.rstrip("\n\r")
        if not line.strip():
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        m = re.fullmatch(r"(.+?)(?:\t+| {2,}|\.{2,}\s*)([0-9]+)\s*", stripped)
        if not m or not m.group(1).strip():
            raise ValueError(
                f"TOC line {number}: expected title, TAB/two spaces/dots, and PDF page"
            )
        title, page = m.group(1).strip(), int(m.group(2)) + offset
        if page < 1:
            raise ValueError(f"TOC line {number}: page out of range: {page}")
        if indent == 0 or not indent_stack:
            level = 0
            indent_stack = [(0, 0)]
        else:
            while indent_stack and indent_stack[-1][0] >= indent:
                indent_stack.pop()
            if indent_stack:
                level = indent_stack[-1][1] + 1
            else:
                level = 0
            indent_stack.append((indent, level))
        entries.append({"title": title, "page": page, "level": level})
    return entries


def build_tree_from_entries(entries):
    tree = []
    stack = []
    for entry in entries:
        page = entry["page"]
        title = entry["title"]
        level = entry["level"]
        while stack and stack[-1][1] >= level:
            stack.pop()
        parent_idx = stack[-1][0] if stack else -1
        tree.append((page, title, parent_idx))
        stack.append((len(tree) - 1, level))
    return tree


def build_tree_from_headings(headings):
    if not headings:
        return []
    tree = []
    last_chapter = -1
    last_section = -1
    numbered_sections = {}
    for h in headings:
        if h["type"] == "chapter":
            tree.append((h["page"], h["title"], -1))
            last_chapter = len(tree) - 1
            last_section = -1
            numbered_sections = {}
        elif h["type"] == "section":
            parent = last_chapter if last_chapter >= 0 else -1
            tree.append((h["page"], h["title"], parent))
            last_section = len(tree) - 1
            number = re.match(r"^(\d+\.\d+)\s", h["title"])
            if number:
                numbered_sections[number.group(1)] = last_section
        elif h["type"] == "subsection":
            parent = (
                last_section
                if last_section >= 0
                else (last_chapter if last_chapter >= 0 else -1)
            )
            number = re.match(r"^(\d+\.\d+)\.\d+\s", h["title"])
            if number:
                parent = numbered_sections.get(number.group(1), parent)
            tree.append((h["page"], h["title"], parent))
    return tree


def add_bookmarks(pdf_path, tree, output_path, verification="structural"):
    if Path(pdf_path).resolve() == Path(output_path).resolve():
        raise ValueError("Output must differ from input PDF")
    import fitz

    doc = fitz.open(pdf_path)
    toc = []
    node_levels = {}
    for idx, (page_num, title, parent_idx) in enumerate(tree):
        if not 1 <= page_num <= doc.page_count:
            doc.close()
            raise ValueError(f"Bookmark page out of range: {page_num}")
        if parent_idx == -1:
            level = 1
        else:
            if parent_idx not in node_levels:
                doc.close()
                raise ValueError("Bookmark parent must precede its child")
            parent_level = node_levels[parent_idx]
            level = parent_level + 1
        node_levels[idx] = level
        toc.append([level, title, page_num])
    doc.set_toc(toc)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    handle, temporary = tempfile.mkstemp(suffix=".pdf", dir=Path(output_path).parent)
    os.close(handle)
    try:
        doc.save(temporary, deflate=True)
        doc.close()
        valid = (
            verify_content(pdf_path, temporary)
            if verification == "structural"
            else verify_content(pdf_path, temporary, render=True)
        )
        if not valid:
            raise ValueError("Content verification failed")
        os.replace(temporary, output_path)
    finally:
        if not doc.is_closed:
            doc.close()
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(toc)


def verify_content(original_path, new_path, render=False):
    """Check preserved streams and navigation; full mode also compares all page pixels."""
    import fitz

    with fitz.open(original_path) as orig, fitz.open(new_path) as new:
        if (
            orig.page_count != new.page_count
            or orig.metadata != new.metadata
            or orig.get_page_labels() != new.get_page_labels()
            or orig.embfile_names() != new.embfile_names()
        ):
            return False
        # Save without renumbering: decoded content/image/font/attachment streams stay equal.
        for xref in range(1, orig.xref_length()):
            if (
                orig.xref_is_stream(xref)
                and orig.xref_get_key(xref, "Type")[1] not in ("/ObjStm", "/XRef")
                and orig.xref_stream(xref) != new.xref_stream(xref)
            ):
                return False
        for name in orig.embfile_names():
            if orig.embfile_get(name) != new.embfile_get(name):
                return False
        for a, b in zip(orig, new, strict=True):
            if (
                a.mediabox != b.mediabox
                or a.cropbox != b.cropbox
                or a.rotation != b.rotation
                or a.get_text() != b.get_text()
                or a.get_links() != b.get_links()
            ):
                return False
            ax = [annot.xref for annot in a.annots() or []]
            bx = [annot.xref for annot in b.annots() or []]
            if ax != bx or any(orig.xref_object(x) != new.xref_object(x) for x in ax):
                return False
            if render and a.get_pixmap().samples != b.get_pixmap().samples:
                return False
        return True


def _read_image_page(task):
    from collections import defaultdict
    from statistics import median

    import fitz
    import pytesseract
    from PIL import Image

    if len(task) == 5:
        pdf_path, index, lang, cmd, extended = task
        dpi = 200
    else:
        pdf_path, index, lang, cmd, extended, dpi = task
    os.environ["OMP_THREAD_LIMIT"] = "1"
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    with fitz.open(pdf_path) as doc:
        pix = doc[index].get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    data = pytesseract.image_to_data(
        image, lang=lang, timeout=120, output_type=pytesseract.Output.DICT
    )
    lines = defaultdict(list)
    heights = []
    for i, word in enumerate(data["text"]):
        if word.strip() and (
            float(data["conf"][i]) >= 40 or re.fullmatch(r"[IVXLCDM]+\.?", word)
        ):
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines[key].append(i)
            heights.append(data["height"][i])
    baseline = median(heights) if heights else 0
    text_lines, titles = [], []
    for indices in lines.values():
        line = " ".join(data["text"][i] for i in indices)
        top = min(data["top"][i] for i in indices)
        if top < image.height * 0.06 or top > image.height * 0.96:
            continue
        text_lines.append(line)
        if (
            baseline
            and median(data["height"][i] for i in indices)
            >= baseline * (1.2 if extended else 1.4)
            and 3 <= len(line) <= 100
            and (len(indices) >= 2 or len(line) >= 5)
            and not re.search(r"[。！？!?]|[.!]$", line)
        ):
            titles.append(line)
    # Sparse illustrated Chinese chapter openers can be skipped by automatic layout detection.
    if (
        "chi" in lang
        and len(re.sub(r"\s", "", "".join(text_lines))) < 250
        and not any(match_heading(line, True) for line in text_lines)
    ):
        sparse = pytesseract.image_to_string(
            image, lang=lang, config="--psm 11", timeout=120
        )
        text_lines.extend(line.strip() for line in sparse.splitlines() if line.strip())
    # Old books often put the chapter number and small-cap title on separate lines.
    merged = []
    for line in text_lines:
        letters = "".join(c for c in line if c.isalpha())
        chinese_open = merged and re.fullmatch(
            r"第[一二三四五六七八九十\d]+章", clean_ocr_line(merged[-1], True)
        )
        if chinese_open and re.fullmatch(r"[\u4e00-\u9fff\s]{2,30}", line):
            merged[-1] += " " + line
            continue
        chapter_open = merged and re.match(
            r"^(Chapter|Part|Appendix)\s+[A-Z0-9]+\.?", merged[-1], re.I
        )
        if (
            chapter_open
            and letters
            and letters.isupper()
            and len(letters) >= 4
            and len(merged[-1]) + len(line) < 120
            and not re.search(r"[=+_{}]", line)
        ):
            merged[-1] += " " + line.rstrip(".")
        else:
            merged.append(line)
    return index + 1, "\n".join(merged), titles


def read_pages(
    pdf_path,
    lang="chi_sim+eng",
    force_ocr=False,
    workers=None,
    extended=False,
    dpi=200,
    allow_partial=False,
    warnings=None,
):
    import fitz

    with fitz.open(pdf_path) as doc:
        if doc.is_encrypted:
            raise ValueError("Encrypted PDF requires an unlocked copy")
        if not doc.page_count:
            raise ValueError("PDF has no pages")
        pages, visual = [], {}
        from statistics import median

        for i, page in enumerate(doc):
            raw = [
                line
                for block in page.get_text(
                    "dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
                )["blocks"]
                if "lines" in block
                for line in block["lines"]
            ]
            sizes = [
                span["size"]
                for line in raw
                for span in line["spans"]
                if span["text"].strip()
            ]
            baseline = median(sizes) if sizes else 0
            # PDF extractors often split a section number and its title on the same row.
            rows = []
            for line in sorted(
                raw, key=lambda line: (round(line["bbox"][1], 1), line["bbox"][0])
            ):
                title = "".join(span["text"] for span in line["spans"]).strip()
                if not title:
                    continue
                size = max(span["size"] for span in line["spans"])
                bold = all(
                    span["flags"] & 16 for span in line["spans"] if span["text"].strip()
                )
                y, bottom = line["bbox"][1], line["bbox"][3]
                if rows and abs(rows[-1][1] - y) < 2:
                    rows[-1][0] = (
                        title + " " + rows[-1][0]
                        if line["bbox"][0] < rows[-1][5]
                        else rows[-1][0] + " " + title
                    )
                    rows[-1][5] = min(rows[-1][5], line["bbox"][0])
                    rows[-1][2] = max(rows[-1][2], size)
                    rows[-1][3] &= bold
                else:
                    rows.append([title, y, size, bold, bottom, line["bbox"][0]])
            # Ignore printed TOC pages rather than linking to their duplicate titles.
            normalized_rows = [clean_ocr_line(row[0]) for row in rows]
            is_contents = any(
                re.fullmatch(r"Contents|Table of Contents|目\s*录", title, re.I)
                for title in normalized_rows
            ) and (
                sum(". ." in title or "..." in title for title in normalized_rows) >= 3
                or sum(
                    bool(re.fullmatch(r"[0-9]+", title)) for title in normalized_rows
                )
                >= 3
            )
            # Continuation TOC pages still have many detached page numbers and very little prose.
            is_contents |= (
                sum(bool(re.fullmatch(r"[0-9]+", title)) for title in normalized_rows)
                >= 10
                and sum(len(title) > 60 for title in normalized_rows) < 2
            )
            merged = []
            for row in rows:
                if merged:
                    previous = merged[-1]
                    stub = re.fullmatch(
                        r"(?:Chapter|Part|Appendix)\s+(?:[0-9]+|[A-Z]+)\.?",
                        previous[0],
                        re.I,
                    )
                    wrap = (
                        previous[2] > baseline * 1.2
                        and abs(previous[2] - row[2]) < 1
                        and row[1] - previous[4] < row[2]
                    )
                    if (
                        stub
                        and row[2] > baseline * 1.2
                        and row[1] - previous[4] < row[2] * 3
                    ) or wrap:
                        previous[0] += " " + row[0]
                        previous[2] = max(previous[2], row[2])
                        previous[4] = row[4]
                        continue
                merged.append(row)
            text = "\n".join(r[0] for r in merged)
            pages.append((i + 1, text))
            for title, _y, size, bold, _bottom, _x in merged:
                if is_contents:
                    continue
                prominent = (
                    size >= max(14, baseline * 1.2) or (len(rows) <= 3 and size >= 14)
                ) or (extended and size >= baseline and bold)
                if (
                    prominent
                    and 3 <= len(title) <= 100
                    and not re.fullmatch(r"[\d.]+", title)
                    and not re.search(r"[。！!]|[.!]$", title)
                ):
                    visual.setdefault(i + 1, []).append(title)
        # OCR pages containing images but little useful text (including mixed PDFs).
        scanned = [
            i
            for i, page in enumerate(doc)
            if force_ocr
            or (len(re.sub(r"\s", "", pages[i][1])) < 40 and page.get_images())
        ]
    if scanned:
        import pytesseract

        reason = None
        if not ensure_tesseract():
            reason = "Tesseract not found or unusable; install it for scanned pages"
        else:
            missing = set(lang.split("+")) - set(pytesseract.get_languages())
            if missing:
                reason = "Missing OCR languages: " + ", ".join(sorted(missing))
        if reason:
            if not allow_partial:
                raise ValueError(reason)
            message = f"{reason}; skipped {len(scanned)} scanned pages"
            if warnings is not None:
                warnings.append(message)
            print("Warning: " + message)
            scanned = []
        else:
            print(f"OCR required for {len(scanned)}/{len(pages)} pages.")
            tasks = [
                (pdf_path, i, lang, find_tesseract(), extended, dpi) for i in scanned
            ]
            with ProcessPoolExecutor(
                max_workers=workers or min(4, os.cpu_count() or 1, len(tasks))
            ) as pool:
                for done, (number, text, titles) in enumerate(
                    pool.map(_read_image_page, tasks), 1
                ):
                    pages[number - 1] = (number, text)
                    visual[number] = titles
                    if done % max(1, len(tasks) // 5) == 0 or done == len(tasks):
                        print(f"OCR progress: {done}/{len(tasks)}")
    else:
        print("Text-based PDF detected. Extracting headings...")
    return pages, set(i + 1 for i in scanned), visual


def headings_from_pages(pages, scanned, pdf_type="auto", visual=None):
    from collections import Counter

    # Repeated marginal lines are page headers/footers, not chapter starts.
    def marginal_key(line):
        return re.sub(r"\s+\d+$", "", re.sub(r"^\d+\s+", "", clean_ocr_line(line)))

    margins = Counter()
    for _, text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        margins.update({marginal_key(line) for line in lines[:2] + lines[-2:]})
    headings = []
    for number, text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        normalized = [clean_ocr_line(line, number in scanned) for line in lines]
        numbered = sum(
            bool(re.match(r"^\d+\.\d+\s+[A-Za-z\u4e00-\u9fff]", line))
            for line in normalized
        )
        if (
            numbered >= 2
            and any(
                re.fullmatch(r"目\s*录|Contents|Table of Contents", line, re.I)
                for line in normalized
            )
        ) or (
            numbered >= 8
            and sum(bool(re.search(r"\d+$|\.{3,}", line)) for line in normalized) >= 5
        ):
            continue
        for raw_line in lines:
            line = clean_ocr_line(raw_line, number in scanned)
            if re.match(r"^[一二三四五六七八九十]+、", line):
                line = re.split(r"[:：]", line, maxsplit=1)[0].strip()
            if (
                len(pages) >= 3
                and margins[marginal_key(line)] >= max(3, len(pages) * 0.05)
                and raw_line not in (visual or {}).get(number, [])
            ):
                continue
            if re.search(r"[。！!]|\.{3,}.*\d+$", line) or len(line) > 100:
                continue
            if (
                visual is not None
                and number not in scanned
                and raw_line not in visual.get(number, [])
            ):
                continue
            if re.match(r"^\d+\.\d+", line) and re.search(r"[=+*/]", line):
                continue
            entry = match_heading(line, number in scanned, pdf_type)
            if (
                entry
                and entry["type"] == "chapter"
                and number in scanned
                and re.match(r"^\d+[.)]?\s+", clean_ocr_line(line))
                and not re.match(r"^20\d{2}\s*年", line)
                and raw_line not in (visual or {}).get(number, [])
            ):
                continue
            if (
                entry
                and number in scanned
                and re.match(r"^(Chapter|Part|Appendix)\b", line, re.I)
                and raw_line not in (visual or {}).get(number, [])
                and sum(c.isupper() for c in line)
                < sum(c.isalpha() for c in line) * 0.8
            ):
                continue
            if (
                not entry
                and pdf_type != "exam"
                and raw_line in (visual or {}).get(number, [])
                and not match_heading(line, number in scanned, "auto")
                and re.match(r"[A-Z\u4e00-\u9fff]", line)
                and len(line) <= 50
                and not re.search(r"[=+_*{}\[\]。?!]|[.,]$", line)
                and (
                    number not in scanned
                    or re.fullmatch(r"[\u4e00-\u9fff、， ()\-]{3,40}", line)
                    or (
                        len(re.findall(r"[A-Z][a-z]{2,}|[A-Z]{3,}", line)) >= 2
                        and not re.search(r"[=+_*{}\[\]\d]", line)
                    )
                )
            ):
                numbered_chapter = any(
                    h["type"] == "chapter"
                    and re.match(
                        r"^(?:Chapter|Part|Appendix)\b|^第.*章|^\d+\s", h["title"], re.I
                    )
                    for h in headings
                )
                entry = {
                    "type": "section"
                    if numbered_chapter
                    and not re.fullmatch(
                        r"Index|Contents|Preface|前言|序言|目录|附录", line, re.I
                    )
                    else "chapter",
                    "title": clean_ocr_line(line, number in scanned),
                }
            if entry:
                headings.append(dict(entry, page=number))
    return filter_headings(headings, len(pages))


def main():
    parser = argparse.ArgumentParser(
        description="Add hierarchical bookmarks to PDF files"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("input")
    parser.add_argument("-o", "--output")
    parser.add_argument("--lang", default="chi_sim+eng")
    parser.add_argument("--force-ocr", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--toc")
    modes.add_argument("--analyze", action="store_true")
    modes.add_argument("--generate-toc", action="store_true")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--workers", type=int)
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="OCR render DPI (lower = faster, default 200)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit structured JSON result on stdout"
    )
    parser.add_argument(
        "--type",
        choices=["auto", "textbook", "exam", "slides", "article"],
        default="auto",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow text-only results when OCR is unavailable",
    )
    parser.add_argument(
        "--verify",
        choices=["structural", "full"],
        default="structural",
        help="Preservation check; full also renders every page",
    )
    json_mode = "--json" in sys.argv[1:]
    try:
        with redirect_stdout(sys.stderr if json_mode else sys.stdout):
            args = parser.parse_args()
            result = execute(args)
    except (Exception, SystemExit) as error:
        if isinstance(error, SystemExit) and error.code == 0:
            return 0
        result = {
            "ok": False,
            "error": str(error)
            if not isinstance(error, SystemExit)
            else "Invalid command-line arguments",
        }
    if json_mode:
        print(json.dumps(result, ensure_ascii=True))
    elif not result["ok"]:
        print(f"Error: {result['error']}")
    return 0 if result["ok"] else 1


def execute(args):
    if args.workers is not None and args.workers < 1:
        raise ValueError("--workers must be positive")
    if not 72 <= args.dpi <= 600:
        raise ValueError("--dpi must be between 72 and 600")
    warnings = []
    result = {
        "ok": True,
        "mode": "analyze" if args.analyze else "bookmarks",
        "type": args.type,
        "partial": False,
        "warnings": warnings,
    }
    source = Path(args.input)
    if not source.is_file():
        raise ValueError(f"File not found: {source}")
    output = (
        Path(args.output)
        if args.output
        else source.with_name(source.stem + "_with_bookmarks.pdf")
    )
    if output.resolve() == source.resolve():
        raise ValueError("Output must differ from input PDF")
    if args.toc:
        if not Path(args.toc).is_file():
            raise ValueError(f"TOC file not found: {args.toc}")
        entries = parse_toc_file(args.toc, args.offset)
        if not entries:
            raise ValueError("No entries found in TOC file")
        print(f"Found {len(entries)} TOC entries.")
        tree = build_tree_from_entries(entries)
    else:
        pages, scanned, visual = read_pages(
            str(source),
            args.lang,
            args.force_ocr,
            args.workers,
            args.generate_toc,
            args.dpi,
            args.allow_partial,
            warnings,
        )
        result.update(pages=len(pages), ocr_pages=len(scanned), partial=bool(warnings))
        # Auto keeps all supported patterns; explicit types restrict the rules.
        headings = headings_from_pages(pages, scanned, args.type, visual)
        print(f"Heading profile: {args.type}")
        if args.analyze or args.generate_toc:
            toc_path = source.with_name(source.stem + "_suggested_toc.txt")
            levels, rows = {}, []
            for index, (page, title, parent) in enumerate(
                build_tree_from_headings(headings)
            ):
                levels[index] = levels[parent] + 1 if parent >= 0 else 0
                rows.append("  " * levels[index] + f"{title}\t{page}\n")
            toc_path.write_text("".join(rows), encoding="utf-8")
            print(f"Suggested TOC written to: {toc_path}")
            print(f"Total pages: {len(pages)} | Candidates found: {len(headings)}")
            result.update(
                toc=str(toc_path), candidates=len(headings), headings=headings
            )
            if args.analyze:
                return result
        if not headings:
            raise ValueError(
                "No headings detected. Review with --analyze and provide a --toc file."
            )
        print(f"Found {len(headings)} headings.")
        tree = build_tree_from_headings(headings)
    count = add_bookmarks(str(source), tree, str(output), args.verify)
    result.update(bookmarks=count, output=str(output), verification=args.verify)
    if not args.json:
        print(
            f"Added {count} bookmarks.\nContent verified ({args.verify}).\nOutput: {output}"
        )
    return result


if __name__ == "__main__":
    sys.exit(main())
