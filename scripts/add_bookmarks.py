#!/usr/bin/env python3
import sys, os, re, io, argparse, shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

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

def match_heading(line, ocr_mode=False):
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
    # Exam patterns: year-based headings like "2026年真题", "2009年应用题"
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
        if htype == "chapter" and len(title) > 30:
            continue

        # Reject suspicious bare-number chapters on last 2 pages with long titles
        if htype == "chapter" and page >= total_pages - 1:
            m = re.match(r'^(\d+)\s+(.+)', title)
            if m and len(m.group(2)) > 6:
                continue

        # Deduplicate: if same title seen before, replace with later occurrence
        # (later page is more likely to be the actual heading)
        if title in seen_titles:
            idx = seen_titles[title]
            if page > filtered[idx]["page"]:
                filtered[idx] = h
            continue

        seen_titles[title] = len(filtered)
        filtered.append(h)

    return filtered

def detect_pdf_type(pdf_path):
    """Auto-detect PDF type: textbook, exam, slides, article, or unknown."""
    import fitz
    doc = fitz.open(pdf_path)
    sample_pages = min(10, doc.page_count)
    sample_text = ""
    for i in range(sample_pages):
        sample_text += (doc[i].get_text() or "") + "\n"
    doc.close()
    stripped = sample_text.strip()
    if len(stripped) < 50:
        return {"type": "unknown", "confidence": 0.0, "reason": "Image-based PDF (no extractable text)"}
    lines = [l.strip() for l in stripped.split("\n") if l.strip()]
    textbook_score = exam_score = slides_score = article_score = 0
    for line in lines:
        if re.search(r'第[一二三四五六七八九十\d]+[章节篇]', line): textbook_score += 2
        elif re.match(r'^\d+\.\d+[\.\s]', line): textbook_score += 1
        elif re.match(r'^(Chapter|Section)\s+\d+', line, re.I): textbook_score += 2
        if re.search(r'20\d{2}\s*年.*(真|应|考|试|题|统考)', line): exam_score += 2
        elif re.search(r'(真题|统考|试题卷|模拟题)', line): exam_score += 2
        elif re.search(r'20\d{2}.*题$', line): exam_score += 1
        elif re.match(r'第\d+讲', line): exam_score += 1
        if re.match(r'^[•·▪\-]\s', line): slides_score += 1
        if re.match(r'^[一二三四五六七八九十]+[、.]\s', line): slides_score += 1
        if re.search(r'(摘要|引言|前言|[Ii]ntroduction|[Cc]onclusion|参考文献|[Rr]eferences)', line):
            article_score += 1
    scores = {"textbook": textbook_score, "exam": exam_score,
              "slides": slides_score, "article": article_score}
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / max(total, 1)
    if confidence < 0.3:
        return {"type": "unknown", "confidence": confidence, "reason": "Mixed or unclear patterns"}
    reasons = {"textbook": "Chapter/section numbering detected",
               "exam": "Exam year/question patterns detected",
               "slides": "Bullet/short slide-style lines detected",
               "article": "Abstract/intro/conclusion structure detected"}
    return {"type": best, "confidence": confidence, "reason": reasons[best]}

def is_text_based(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    sample_text = ""
    for i in range(min(5, doc.page_count)):
        t = (doc[i].get_text() or "").strip()
        sample_text += t + "\n"
    doc.close()
    if len(sample_text) < 100: return False
    lines = sample_text.split("\n")
    heading_count = sum(1 for l in lines if match_heading(l.strip()))
    if heading_count > 0: return True
    if len(set(sample_text)) < 10: return False
    return True

def extract_headings_text(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    headings = []
    for i in range(doc.page_count):
        text = doc[i].get_text() or ""
        for line in text.split("\n"):
            entry = match_heading(line.strip())
            if entry:
                entry["page"] = i + 1
                headings.append(entry)
    total = doc.page_count
    doc.close()
    return filter_headings(headings, total_pages=total)

def _ocr_page_range(args):
    pdf_path, start_page, end_page, lang, tesseract_cmd, dpi = args
    import fitz, pytesseract
    from PIL import Image
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    doc = fitz.open(pdf_path)
    results = []
    for i in range(start_page, min(end_page, doc.page_count)):
        try:
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang=lang)
            # Only check first 15 lines to avoid body text false positives
            for line in text.split("\n")[:15]:
                line = line.strip()
                if not line: continue
                entry = match_heading(line, ocr_mode=True)
                if entry:
                    entry["page"] = i + 1
                    results.append(entry)
        except Exception as e:
            print(f"  Warning: OCR failed on page {i+1}: {e}", file=sys.stderr)
    doc.close()
    return results

def extract_headings_ocr(pdf_path, lang="chi_sim+eng", max_workers=None, dpi=200):
    import fitz
    doc = fitz.open(pdf_path)
    total = doc.page_count
    doc.close()
    if total == 0: return []
    tesseract_cmd = find_tesseract()
    batch_size = max(10, min(20, total // max(1, (max_workers or os.cpu_count() or 4))))
    ranges = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        ranges.append((pdf_path, start, end, lang, tesseract_cmd, dpi))
    workers = max_workers or min(os.cpu_count() or 4, len(ranges))
    print(f"Processing {total} pages with OCR using {workers} workers...")
    headings = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_ocr_page_range, r): r for r in ranges}
        completed = 0
        for future in as_completed(futures):
            try:
                result = future.result()
                headings.extend(result)
            except Exception as e:
                r = futures[future]
                print(f"  Warning: batch pages {r[1]+1}-{r[2]} failed: {e}", file=sys.stderr)
            completed += 1
            if completed % max(1, len(ranges) // 5) == 0:
                print(f"  {completed}/{len(ranges)} batches done...")
    # Sort by page before filtering/building tree
    headings.sort(key=lambda x: (x["page"], x.get("_order", 0)))
    return filter_headings(headings, total_pages=total)

def _ocr_page_range_full(args):
    """OCR pages and return full (page_num, text) tuples (for analyze/generate-toc)."""
    pdf_path, start_page, end_page, lang, tesseract_cmd, dpi = args
    import fitz, pytesseract
    from PIL import Image
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    doc = fitz.open(pdf_path)
    results = []
    for i in range(start_page, min(end_page, doc.page_count)):
        try:
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang=lang)
            results.append((i + 1, text))
        except Exception as e:
            print(f"  Warning: OCR failed on page {i+1}: {e}", file=sys.stderr)
            results.append((i + 1, ""))
    doc.close()
    return results

def ocr_all_pages(pdf_path, lang="chi_sim+eng", max_workers=None, dpi=200):
    """OCR all pages in parallel, return list of (page_num, text)."""
    import fitz
    doc = fitz.open(pdf_path)
    total = doc.page_count
    doc.close()
    if total == 0: return []
    tesseract_cmd = find_tesseract()
    batch_size = max(10, min(20, total // max(1, (max_workers or os.cpu_count() or 4))))
    ranges = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        ranges.append((pdf_path, start, end, lang, tesseract_cmd, dpi))
    workers = max_workers or min(os.cpu_count() or 4, len(ranges))
    print(f"OCR processing {total} pages with {workers} workers...")
    all_text = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_ocr_page_range_full, r): r for r in ranges}
        completed = 0
        for future in as_completed(futures):
            try:
                all_text.extend(future.result())
            except Exception as e:
                r = futures[future]
                print(f"  Warning: batch pages {r[1]+1}-{r[2]} failed: {e}", file=sys.stderr)
            completed += 1
            if completed % max(1, len(ranges) // 5) == 0:
                print(f"  {completed}/{len(ranges)} batches done...")
    all_text.sort(key=lambda x: x[0])
    return all_text

def extract_all_text(pdf_path):
    """Extract text from all pages (text-based PDFs)."""
    import fitz
    doc = fitz.open(pdf_path)
    all_text = [(i + 1, doc[i].get_text() or "") for i in range(doc.page_count)]
    doc.close()
    return all_text

def generate_candidate_toc(all_text, ocr_mode=False):
    """Generate candidate TOC entries from full page text."""
    headings = []
    for page_num, text in all_text:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        found = False
        # Try existing heading patterns on first 15 lines
        for line in lines[:15]:
            entry = match_heading(line, ocr_mode=ocr_mode)
            if entry:
                entry["page"] = page_num
                headings.append(entry)
                found = True
                break
        if found:
            continue
        # Fallback: find a short title-like line
        best_line = None
        for line in lines[:10]:
            cleaned = clean_ocr_line(line, ocr_mode=ocr_mode)
            if len(cleaned) < 3 or len(cleaned) > 40:
                continue
            # Prefer lines with Chinese characters
            cn_count = sum(1 for c in cleaned if '\u4e00' <= c <= '\u9fff')
            # Or lines with year numbers
            has_year = bool(re.search(r'20\d{2}', cleaned))
            if cn_count >= 2 or has_year:
                best_line = cleaned
                break
        if best_line:
            headings.append({"type": "chapter", "title": best_line, "page": page_num})
    return headings

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
        page = max(1, entry["page"])
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
        page_num = max(1, min(page_num, doc.page_count))
        if parent_idx == -1:
            level = 1
        else:
            parent_level = node_levels.get(parent_idx, 1)
            level = parent_level + 1
        node_levels[idx] = level
        toc.append([level, title, page_num])
    doc.set_toc(toc)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    return len(toc)

def verify_content(original_path, new_path):
    import fitz
    orig = fitz.open(original_path)
    new = fitz.open(new_path)
    if orig.page_count != new.page_count:
        orig.close(); new.close()
        return False
    check_indices = [0]
    if orig.page_count > 1: check_indices.append(orig.page_count // 2)
    if orig.page_count > 2: check_indices.append(orig.page_count - 1)
    for i in sorted(set(check_indices)):
        if orig[i].get_text() != new[i].get_text():
            orig.close(); new.close()
            return False
    orig.close(); new.close()
    return True

def main():
    parser = argparse.ArgumentParser(description="Add hierarchical bookmarks to PDF files")
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("-o", "--output", help="Output PDF path (default: *_with_bookmarks.pdf)")
    parser.add_argument("--lang", default="chi_sim+eng", help="Tesseract OCR language")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR mode")
    parser.add_argument("--toc", help="TOC text file path (title+page per line)")
    parser.add_argument("--offset", type=int, default=0, help="Page offset for TOC mode")
    parser.add_argument("--workers", type=int, default=None, help="Number of OCR worker processes")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze PDF: OCR all pages, show content summary, generate suggested TOC file")
    parser.add_argument("--generate-toc", action="store_true",
                        help="Auto-generate TOC by OCR+analyzing all pages, then add bookmarks")
    parser.add_argument("--type", choices=["auto", "textbook", "exam", "slides", "article"],
                        default="auto", help="PDF type hint (default: auto-detect)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    output_path = args.output or str(input_path.parent / f"{input_path.stem}_with_bookmarks.pdf")

    # --analyze mode: OCR all pages and show content summary
    if args.analyze:
        print(f"Analyzing: {input_path.name}")
        pdf_type = detect_pdf_type(str(input_path))
        print(f"Detected type: {pdf_type['type']} (confidence: {pdf_type['confidence']:.1%}, {pdf_type['reason']})")
        print()
        use_ocr = args.force_ocr or not is_text_based(str(input_path))
        if use_ocr:
            if not ensure_tesseract():
                print("Error: Tesseract not found.")
                sys.exit(1)
            all_text = ocr_all_pages(str(input_path), lang=args.lang, max_workers=args.workers)
        else:
            all_text = extract_all_text(str(input_path))
            print("Text-based PDF. Extracting text...")
        print()
        print(f"{'Page':>5} | {'Content Preview':<60}")
        print("-" * 70)
        candidates = generate_candidate_toc(all_text, ocr_mode=use_ocr)
        seen_pages = set()
        for h in candidates:
            if h["page"] not in seen_pages:
                preview = h["title"][:60]
                print(f"{h['page']:>5} | {preview:<60}")
                seen_pages.add(h["page"])
        for page_num, text in all_text:
            if page_num not in seen_pages:
                first_line = (text.strip().split("\n")[0] if text.strip() else "(empty)")[:60]
                print(f"{page_num:>5} | {first_line:<60}")
        # Generate suggested TOC file
        toc_path = input_path.parent / f"{input_path.stem}_suggested_toc.txt"
        with open(toc_path, "w", encoding="utf-8") as f:
            for idx, h in enumerate(candidates):
                prefix = "  " if idx > 0 and candidates[idx-1]["page"] != h["page"] else ""
                f.write(f"{prefix}{h['title']} {h['page']}\n")
        print(f"\nSuggested TOC written to: {toc_path}")
        print(f"Total pages: {len(all_text)} | Candidates found: {len(candidates)}")
        return

    # --generate-toc mode: auto-detect, OCR all pages, generate TOC, add bookmarks
    if args.generate_toc:
        print(f"Auto-generating TOC for: {input_path.name}")
        use_ocr = args.force_ocr or not is_text_based(str(input_path))
        if use_ocr:
            if not ensure_tesseract():
                print("Error: Tesseract not found.")
                sys.exit(1)
            all_text = ocr_all_pages(str(input_path), lang=args.lang, max_workers=args.workers)
        else:
            all_text = extract_all_text(str(input_path))
        print("Analyzing page content for candidates...")
        headings = generate_candidate_toc(all_text, ocr_mode=use_ocr)
        if not headings:
            print("Could not identify any page headings even with full analysis.")
            sys.exit(1)
        headings = filter_headings(headings, total_pages=len(all_text))
        print(f"Found {len(headings)} candidate headings from {len(all_text)} pages.")
        tree = build_tree_from_headings(headings)
        count = add_bookmarks(str(input_path), tree, output_path)
        print(f"Added {count} bookmarks.")
        if verify_content(str(input_path), output_path):
            print("Content verified: original pages preserved.")
        print(f"Output: {output_path}")
        return

    # TOC file mode (existing)
    if args.toc:
        toc_path = Path(args.toc)
        if not toc_path.exists():
            print(f"Error: TOC file not found: {args.toc}")
            sys.exit(1)
        print(f"Parsing TOC file: {args.toc}")
        entries = parse_toc_file(str(toc_path), offset=args.offset)
        if not entries:
            print("No entries found in TOC file.")
            sys.exit(1)
        print(f"Found {len(entries)} TOC entries.")
        tree = build_tree_from_entries(entries)
        count = add_bookmarks(str(input_path), tree, output_path)
        print(f"Added {count} bookmarks.")
        print(f"Output: {output_path}")
        return

    # Auto-detect mode (existing)
    use_ocr = args.force_ocr or not is_text_based(str(input_path))

    if use_ocr:
        print("Image-based PDF detected. Using OCR...")
        if not ensure_tesseract():
            print("Error: Tesseract not found. See references/dependencies.md")
            sys.exit(1)
        headings = extract_headings_ocr(str(input_path), lang=args.lang, max_workers=args.workers)
        # Smart fallback: if OCR found 0 headings, do full page analysis
        if not headings:
            print("No headings found via standard OCR. Attempting full-page content analysis...")
            all_text = ocr_all_pages(str(input_path), lang=args.lang, max_workers=args.workers)
            headings = generate_candidate_toc(all_text, ocr_mode=True)
            if headings:
                headings = filter_headings(headings, total_pages=len(all_text))
                # Also save candidate TOC for user reference
                toc_path = input_path.parent / f"{input_path.stem}_suggested_toc.txt"
                with open(toc_path, "w", encoding="utf-8") as f:
                    for h in headings:
                        f.write(f"{h['title']} {h['page']}\n")
                print(f"Candidate TOC saved to: {toc_path} (edit and re-run with --toc)")
    else:
        print("Text-based PDF detected. Extracting headings...")
        headings = extract_headings_text(str(input_path))

    if not headings:
        print("No headings detected. Try --force-ocr, --generate-toc, or provide a --toc file.")
        sys.exit(1)

    print(f"Found {len(headings)} headings.")
    tree = build_tree_from_headings(headings)
    count = add_bookmarks(str(input_path), tree, output_path)
    print(f"Added {count} bookmarks.")

    if verify_content(str(input_path), output_path):
        print("Content verified: original pages preserved.")
    else:
        print("Warning: content verification failed.")

    print(f"Output: {output_path}")

if __name__ == "__main__":
    main()
