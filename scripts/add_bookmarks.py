#!/usr/bin/env python3
import sys, os, re, argparse, shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

def find_tesseract():
    path = shutil.which("tesseract")
    if path: return path
    if sys.platform == "win32":
        for c in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
            if os.path.exists(c): return c
    elif sys.platform == "darwin":
        for c in ["/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]:
            if os.path.exists(c): return c
    else:
        for c in ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.exists(c): return c
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
            return True
    return False

def clean_ocr_line(line, ocr_mode=False):
    cleaned = re.sub(r'^[^\w\u4e00-\u9fff\d\u3000-\u303f\uff00-\uffef]+', '', line).strip()
    # Normalize spaces in "第 X 章" → "第X章"
    cleaned = re.sub(r'第\s+(\d+)\s+章', r'第\1章', cleaned)
    cleaned = re.sub(r'第\s+([一二三四五六七八九十]+)\s+章', r'第\1章', cleaned)
    # Normalize "X .X" → "X.X"
    cleaned = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', cleaned)
    if ocr_mode:
        # Iteratively normalize spaces between Chinese characters (OCR artifact)
        while True:
            new = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', cleaned)
            if new == cleaned:
                break
            cleaned = new
    return cleaned if cleaned else line.strip()

def match_heading(line, ocr_mode=False, pdf_type="auto"):
    result = _match_heading(line, ocr_mode)
    cleaned = clean_ocr_line(line, ocr_mode)
    exam = bool(re.match(r"^(20\d{2}).*(真题|应用题|统考|试题)|^第\d+讲", cleaned))
    outline = bool(re.match(r"^[一二三四五六七八九十]+、|^（[一二三四五六七八九十]+）", cleaned))
    if pdf_type == "textbook" and (exam or outline):
        return None
    if pdf_type == "exam" and not (exam or outline):
        return None
    if pdf_type == "slides" and result and not (outline or re.match(r"^第.*讲|^\d+[.)]\s", cleaned)):
        return None
    if pdf_type in ("auto", "article"):
        if pdf_type == "article" and (exam or outline or re.match(r"^(Chapter|Part|第.*章)", cleaned, re.I)):
            return None
        if re.fullmatch(r"Abstract|Introduction|Background|Methods|Results|Discussion|Conclusions?|References|摘要|引言|方法|结果|讨论|结论|参考文献", cleaned, re.I):
            return {"type": "chapter", "title": cleaned}
    return result

def _match_heading(line, ocr_mode=False):
    line = clean_ocr_line(line, ocr_mode=ocr_mode)
    if not line: return None
    if re.match(r'^第[一二三四五六七八九十]+章\s*', line):
        return {"type": "chapter", "title": line}
    m = re.match(r'^第(\d+)章\s*(.+)', line)
    if m: return {"type": "chapter", "title": line}
    if re.match(r'^(Chapter|Part|Appendix)\s+(\d+|[IVX]+)\b', line, re.IGNORECASE):
        return {"type": "chapter", "title": line}
    m = re.match(r'^(\d+\.\d+\.\d+)\s+(.+)', line)
    if m: return {"type": "subsection", "title": line}
    m = re.match(r'^(\d+\.\d+)\s+([A-Z\u4e00-\u9fff][\w\s\-]{1,60})$', line)
    if m: return {"type": "section", "title": line}
    m = re.match(r'^(\d+)\.\s+([A-Z][A-Za-z].{0,60})$', line)
    if m and 1 <= int(m.group(1)) <= 20: return {"type": "chapter", "title": line}
    m = re.match(r'^(\d+)\s+([\u4e00-\u9fff][\u4e00-\u9fff\s]{0,15})$', line)
    if m and 2 <= int(m.group(1)) <= 20: return {"type": "chapter", "title": line}
    m = re.match(r'^(\d+)\s+([A-Z][A-Za-z\s\-]{2,40})$', line)
    if m and 2 <= int(m.group(1)) <= 20: return {"type": "chapter", "title": line}
    if re.match(r'^[A-Z]\.\d+\.?\s+\w+', line):
        return {"type": "subsection", "title": line}
    # Match generic year-prefixed examination headings.
    m = re.match(r'^(20\d{2})\s*年.*(?:真题|应用题|统考|试题)', line)
    if m: return {"type": "chapter", "title": line}
    m = re.match(r'^(20\d{2})[年\s]*.*[真应考]题', line)
    if m: return {"type": "chapter", "title": line}
    # Lecture patterns: "第X讲"
    if re.match(r'^第\d+讲\s*', line):
        return {"type": "chapter", "title": line}
    # Outline markers: "一、", "（一）", "1." at line start for slides/outlines
    if re.match(r'^[一二三四五六七八九十]+[、]', line):
        return {"type": "section", "title": line}
    if re.match(r'^（[一二三四五六七八九十]+）', line):
        return {"type": "section", "title": line}
    return None

def _is_garbage_title(title):
    """Detect OCR garbage titles."""
    if len(title) < 2:
        return True
    # Count non-standard characters (not Chinese, not English letter, not digit, not common punctuation)
    non_standard = sum(1 for c in title if not (c.isalnum() or c.isspace() or c in '._()-，、：:；'))
    if len(title) > 0 and non_standard / len(title) > 0.4:
        return True
    return False

def _is_body_text_word(title):
    """Reject common body text words that shouldn't be chapter titles."""
    body_words = {'注意', '本章', '上述', '下面', '其中', '因此', '所以', '但是', '例如', '比如',
                  '总之', '此外', '另外', '首先', '其次', '最后', '结论', '摘要'}
    # Normalize spaces first (OCR often inserts spaces between Chinese chars)
    normalized = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', title)
    stripped = re.sub(r'^\d+\s*\.?\s*', '', normalized).strip()
    if stripped in body_words:
        return True
    return False

def _is_introduction_text(title):
    """Reject body text that mentions chapters but isn't a real heading."""
    # Only reject the specific pattern "第X章 : XXX" — not all parentheses (exam years use them)
    if re.match(r'^第[一二三四五六七八九十]+章\s*[:：]\s', title):
        return True
    return False

def filter_headings(headings, total_pages=None):
    """Post-process: remove false positives, garbage, duplicates."""
    if not headings:
        return []
    if total_pages is None:
        total_pages = max(h["page"] for h in headings) if headings else 0
    filtered = []
    seen_titles = {}  # title -> index in filtered

    for h in headings:
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

        # Keep the first occurrence; repeated running headers must not move destinations.
        if title in seen_titles:
            idx = seen_titles[title]
            if page < filtered[idx]["page"]:
                filtered[idx] = h
            continue

        seen_titles[title] = len(filtered)
        filtered.append(h)

    return filtered


def parse_toc_file(toc_path, offset=0):
    with open(toc_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    indent_stack = []
    for line in lines:
        line = line.rstrip("\n\r")
        if not line.strip(): continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        m = re.search(r"(\d+)\s*$", stripped)
        if m:
            page = int(m.group(1)) + offset
            title = stripped[:m.start()].strip()
        else:
            page = 1
            title = stripped
        if not title: continue
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
        level = min(level, 3)
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
    if not headings: return []
    tree = []
    last_chapter = -1
    last_section = -1
    for h in headings:
        if h["type"] == "chapter":
            tree.append((h["page"], h["title"], -1))
            last_chapter = len(tree) - 1
            last_section = -1
        elif h["type"] == "section":
            parent = last_chapter if last_chapter >= 0 else -1
            tree.append((h["page"], h["title"], parent))
            last_section = len(tree) - 1
        elif h["type"] == "subsection":
            parent = last_section if last_section >= 0 else (last_chapter if last_chapter >= 0 else -1)
            tree.append((h["page"], h["title"], parent))
    return tree

def add_bookmarks(pdf_path, tree, output_path):
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
            parent_level = node_levels.get(parent_idx, 1)
            level = parent_level + 1
        node_levels[idx] = level
        toc.append([level, title, page_num])
    doc.set_toc(toc)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    handle, temporary = tempfile.mkstemp(suffix=".pdf", dir=Path(output_path).parent)
    os.close(handle)
    try:
        doc.save(temporary, garbage=4, deflate=True)
        doc.close()
        if not verify_content(pdf_path, temporary):
            raise ValueError("Content verification failed")
        os.replace(temporary, output_path)
    finally:
        if not doc.is_closed:
            doc.close()
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(toc)

def verify_content(original_path, new_path):
    import fitz
    orig = fitz.open(original_path)
    new = fitz.open(new_path)
    if orig.page_count != new.page_count:
        orig.close(); new.close()
        return False
    for i in range(orig.page_count):
        if (orig[i].get_text() != new[i].get_text() or
                orig[i].get_pixmap().samples != new[i].get_pixmap().samples):
            orig.close(); new.close()
            return False
    orig.close(); new.close()
    return True

def _read_image_page(task):
    import fitz, pytesseract
    from PIL import Image
    from collections import defaultdict
    from statistics import median
    pdf_path, index, lang, cmd = task
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    with fitz.open(pdf_path) as doc:
        pix = doc[index].get_pixmap(dpi=200, colorspace=fitz.csRGB, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    data = pytesseract.image_to_data(image, lang=lang, timeout=120,
                                     output_type=pytesseract.Output.DICT)
    lines = defaultdict(list)
    heights = []
    for i, word in enumerate(data["text"]):
        if word.strip() and float(data["conf"][i]) >= 40:
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines[key].append(i)
            heights.append(data["height"][i])
    baseline = median(heights) if heights else 0
    text_lines, titles = [], []
    for indices in lines.values():
        line = " ".join(data["text"][i] for i in indices)
        text_lines.append(line)
        if (baseline and median(data["height"][i] for i in indices) >= baseline * 1.4
                and 3 <= len(line) <= 100 and (len(indices) >= 2 or len(line) >= 5)
                and not re.search(r"[。！？!?]|[.!]$", line)):
            titles.append(line)
    return index + 1, "\n".join(text_lines), titles


def read_pages(pdf_path, lang="chi_sim+eng", force_ocr=False, workers=None):
    import fitz
    with fitz.open(pdf_path) as doc:
        if doc.is_encrypted:
            raise ValueError("Encrypted PDF requires an unlocked copy")
        if not doc.page_count:
            raise ValueError("PDF has no pages")
        pages = [(i + 1, page.get_text() or "") for i, page in enumerate(doc)]
        visual = {}
        from statistics import median
        for i, page in enumerate(doc):
            lines = [line for block in page.get_text("dict")["blocks"] if "lines" in block for line in block["lines"]]
            sizes = [span["size"] for line in lines for span in line["spans"] if span["text"].strip()]
            baseline = median(sizes) if sizes else 0
            for line in lines:
                title = "".join(span["text"] for span in line["spans"]).strip()
                size = max((span["size"] for span in line["spans"]), default=0)
                if 3 <= len(title) <= 100 and (size >= max(14, baseline * 1.2) or (len(lines) == 1 and size >= 14)) and not re.search(r"[。！？!?]|[.!]$", title):
                    visual.setdefault(i + 1, []).append(title)
        # OCR pages containing images but little useful text (including mixed PDFs).
        scanned = [i for i, page in enumerate(doc)
                   if force_ocr or (len(re.sub(r"\s", "", pages[i][1])) < 40 and page.get_images())]
    if scanned:
        import pytesseract
        if not ensure_tesseract():
            raise ValueError("Tesseract not found. See SKILL.md")
        available = set(pytesseract.get_languages())
        missing = set(lang.split("+")) - available
        if missing:
            raise ValueError("Missing OCR languages: " + ", ".join(sorted(missing)))
        print(f"OCR required for {len(scanned)}/{len(pages)} pages.")
        cmd = find_tesseract()
        tasks = [(pdf_path, i, lang, cmd) for i in scanned]
        with ProcessPoolExecutor(max_workers=workers or min(4, len(tasks))) as pool:
            for number, text, titles in pool.map(_read_image_page, tasks):
                pages[number - 1] = (number, text)
                visual[number] = titles
    else:
        print("Text-based PDF detected. Extracting headings...")
    return pages, set(i + 1 for i in scanned), visual


def headings_from_pages(pages, scanned, pdf_type="auto", visual=None):
    from collections import Counter
    # Repeated marginal lines are page headers/footers, not chapter starts.
    margins = Counter()
    for _, text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        margins.update(set(lines[:2] + lines[-2:]))
    headings = []
    for number, text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if len(pages) >= 3 and margins[line] >= max(3, len(pages) * 0.6):
                continue
            if re.search(r"[。！？!?]|\.{3,}.*\d+$", line) or len(line) > 100:
                continue
            entry = match_heading(line, number in scanned, pdf_type)
            if (not entry and pdf_type != "exam" and line in (visual or {}).get(number, [])
                    and not match_heading(line, number in scanned, "auto")):
                entry = {"type": "chapter", "title": clean_ocr_line(line, number in scanned)}
            if entry:
                headings.append(dict(entry, page=number))
    return filter_headings(headings, len(pages))


def main():
    parser = argparse.ArgumentParser(description="Add hierarchical bookmarks to PDF files")
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
    parser.add_argument("--type", choices=["auto", "textbook", "exam", "slides", "article"], default="auto")
    args = parser.parse_args()
    try:
        if args.workers is not None and args.workers < 1:
            raise ValueError("--workers must be positive")
        source = Path(args.input)
        if not source.is_file():
            raise ValueError(f"File not found: {source}")
        output = Path(args.output) if args.output else source.with_name(source.stem + "_with_bookmarks.pdf")
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
            pages, scanned, visual = read_pages(str(source), args.lang, args.force_ocr, args.workers)
            # Auto keeps all supported patterns; explicit types restrict the rules.
            headings = headings_from_pages(pages, scanned, args.type, visual)
            print(f"Heading profile: {args.type}")
            if args.analyze:
                toc_path = source.with_name(source.stem + "_suggested_toc.txt")
                levels = {"chapter": 0, "section": 1, "subsection": 2}
                toc_path.write_text("".join("  " * levels[h["type"]] + f"{h['title']} {h['page']}\n" for h in headings), encoding="utf-8")
                print(f"Suggested TOC written to: {toc_path}")
                print(f"Total pages: {len(pages)} | Candidates found: {len(headings)}")
                return 0
            if not headings:
                raise ValueError("No headings detected. Review with --analyze and provide a --toc file.")
            print(f"Found {len(headings)} headings.")
            tree = build_tree_from_headings(headings)
        count = add_bookmarks(str(source), tree, str(output))
        print(f"Added {count} bookmarks.\nContent verified: original pages preserved.\nOutput: {output}")
        return 0
    except Exception as error:
        print(f"Error: {error}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
