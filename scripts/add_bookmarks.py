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

def clean_ocr_line(line):
    cleaned = re.sub(r'^[^\w\u4e00-\u9fff\d]+', '', line).strip()
    # Normalize spaces in "第 X 章" → "第X章"
    cleaned = re.sub(r'第\s+(\d+)\s+章', r'第\1章', cleaned)
    cleaned = re.sub(r'第\s+([一二三四五六七八九十]+)\s+章', r'第\1章', cleaned)
    # Normalize "X .X" → "X.X"
    cleaned = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', cleaned)
    return cleaned if cleaned else line.strip()

def match_heading(line):
    line = clean_ocr_line(line)
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
    return None

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
    doc.close()
    return headings

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
            for line in text.split("\n"):
                line = line.strip()
                if not line: continue
                entry = match_heading(line)
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
    seen = set()
    unique = []
    for h in sorted(headings, key=lambda x: (x["page"], x["title"])):
        key = (h["page"], h["title"])
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique

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
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    output_path = args.output or str(input_path.parent / f"{input_path.stem}_with_bookmarks.pdf")

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

    use_ocr = args.force_ocr or not is_text_based(str(input_path))

    if use_ocr:
        print("Image-based PDF detected. Using OCR...")
        if not ensure_tesseract():
            print("Error: Tesseract not found. See references/dependencies.md")
            sys.exit(1)
        headings = extract_headings_ocr(str(input_path), lang=args.lang, max_workers=args.workers)
    else:
        print("Text-based PDF detected. Extracting headings...")
        headings = extract_headings_text(str(input_path))

    if not headings:
        print("No headings detected. Try --force-ocr.")
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
