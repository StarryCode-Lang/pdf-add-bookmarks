#!/usr/bin/env python3
"""
Add hierarchical bookmarks to PDF files.
Auto-detects text-based vs image-based PDFs.
For scanned PDFs, uses OCR to detect heading structure.

Usage (auto-detect):
    python add_bookmarks.py input.pdf

Usage (TOC file):
    python add_bookmarks.py input.pdf --toc toc.txt [--offset N]

Usage (force OCR):
    python add_bookmarks.py input.pdf --force-ocr
"""

import sys
import os
import re
import io
import argparse
from pathlib import Path


def find_tesseract():
    import shutil
    path = shutil.which("tesseract")
    if path:
        return path
    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    elif sys.platform == "darwin":
        candidates = ["/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]
    else:
        candidates = ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]
    for c in candidates:
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
            return True
    return False


def is_text_based(pdf_path):
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    sample_text = ""
    for i in range(min(5, len(reader.pages))):
        t = (reader.pages[i].extract_text() or "").strip()
        sample_text += t + "\n"
    if len(sample_text) < 100:
        return False
    lines = sample_text.split("\n")
    heading_count = sum(1 for l in lines if match_heading(l.strip()))
    if heading_count > 0:
        return True
    unique_chars = len(set(sample_text))
    if unique_chars < 10:
        return False
    return True


def match_heading(line):
    """Match heading patterns: Chinese and English numbered headings."""
    # Chapter: 第X章 标题
    if re.match(r"^第([一二三四五六七八九十]+)章\s*(.+)", line):
        return {"type": "chapter", "title": line}

    # Chapter: Chapter X, Part X, Appendix X
    if re.match(r"^(Chapter|Part|Appendix)\s+(\d+|[IVX]+)\b", line, re.IGNORECASE):
        return {"type": "chapter", "title": line}

    # Subsection: X.X.X xxx
    m = re.match(r"^(\d+\.\d+\.\d+)\s+(.+)", line)
    if m:
        return {"type": "subsection", "title": line}

    # Section: X.X xxx (title must start with letter or Chinese)
    m = re.match(r"^(\d+\.\d+)\s+([A-Z\u4e00-\u9fff][\w\s\-]{1,60})$", line)
    if m:
        return {"type": "section", "title": line}

    # Chapter: X. Title (English, e.g. "1. Introduction")
    m = re.match(r"^(\d+)\.\s+([A-Z][A-Za-z].{0,60})$", line)
    if m and 1 <= int(m.group(1)) <= 20:
        return {"type": "chapter", "title": line}

    # Chapter: X xxx (Chinese, bare number)
    m = re.match(r"^(\d+)\s+([\u4e00-\u9fff][\u4e00-\u9fff\s]{0,15})$", line)
    if m and 2 <= int(m.group(1)) <= 20:
        return {"type": "chapter", "title": line}

    # Chapter: X Title (English, bare number, capitalized)
    m = re.match(r"^(\d+)\s+([A-Z][A-Za-z\s\-]{2,40})$", line)
    if m and 2 <= int(m.group(1)) <= 20:
        return {"type": "chapter", "title": line}

    # Appendix subsection: A.1. xxx, B.2 xxx
    if re.match(r"^[A-Z]\.\d+\.?\s+\w+", line):
        return {"type": "subsection", "title": line}

    return None


def extract_headings_text(pdf_path):
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    headings = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for line in text.split("\n"):
            entry = match_heading(line.strip())
            if entry:
                entry["page"] = i + 1
                headings.append(entry)
    return headings


def extract_headings_ocr(pdf_path, lang="chi_sim+eng"):
    import fitz, pytesseract
    from PIL import Image

    doc = fitz.open(pdf_path)
    total = doc.page_count
    headings = []
    seen = set()

    print(f"Processing {total} pages with OCR...")
    for i in range(total):
        page = doc[i]
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang=lang)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for line in lines[:15]:
            entry = match_heading(line)
            if entry:
                key = (i + 1, entry["title"])
                if key not in seen:
                    seen.add(key)
                    entry["page"] = i + 1
                    headings.append(entry)

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{total} pages...")

    doc.close()
    return headings


def parse_toc_file(toc_path, offset=0):
    """
    Parse a TOC text file. Format: title + page number per line.
    Indentation (spaces/tabs) determines hierarchy.
    Supports numbered format: 1, 1.1, 1.1.1
    """
    with open(toc_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    entries = []
    for line in lines:
        line = line.rstrip("\n\r")
        if not line.strip():
            continue

        # Count leading spaces for indent level
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Extract page number from end
        m = re.search(r"(\d+)\s*$", stripped)
        if m:
            page = int(m.group(1)) + offset
            title = stripped[:m.start()].strip()
        else:
            page = 1
            title = stripped

        if not title:
            continue

        level = indent // 2 if indent > 0 else 0
        level = min(level, 3)
        entries.append({"title": title, "page": page, "level": level})

    return entries


def build_tree_from_entries(entries):
    """Build outline tree from entries with explicit levels."""
    tree = []
    stack = []  # (index, level)

    for entry in entries:
        page = max(1, entry["page"])
        title = entry["title"]
        level = entry["level"]

        while stack and stack[-1][1] >= level:
            stack.pop()

        if stack:
            parent_idx = stack[-1][0]
        else:
            parent_idx = -1

        tree.append((page, title, parent_idx))
        stack.append((len(tree) - 1, level))

    return tree


def build_tree_from_headings(headings):
    if not headings:
        return []
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
    import pypdf

    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    parent_refs = {}
    for idx, (page_num, title, parent_idx) in enumerate(tree):
        page_num = max(0, min(page_num - 1, len(reader.pages) - 1))
        if parent_idx == -1:
            parent_refs[idx] = writer.add_outline_item(title, page_num, parent=None)
        else:
            parent = parent_refs.get(parent_idx)
            if parent:
                parent_refs[idx] = writer.add_outline_item(title, page_num, parent=parent)

    with open(output_path, "wb") as f:
        writer.write(f)

    return len(tree)


def verify_content(original_path, new_path):
    import pypdf
    orig = pypdf.PdfReader(original_path)
    new = pypdf.PdfReader(new_path)
    if len(orig.pages) != len(new.pages):
        return False
    for i in [0, len(orig.pages) // 2, len(orig.pages) - 1]:
        if orig.pages[i].extract_text() != new.pages[i].extract_text():
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Add hierarchical bookmarks to PDF files")
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("-o", "--output", help="Output PDF path (default: *_with_bookmarks.pdf)")
    parser.add_argument("--lang", default="chi_sim+eng", help="Tesseract OCR language")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR mode")
    parser.add_argument("--toc", help="TOC text file path (title+page per line)")
    parser.add_argument("--offset", type=int, default=0, help="Page offset for TOC mode")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    output_path = args.output or str(input_path.parent / f"{input_path.stem}_with_bookmarks.pdf")

    # TOC file mode
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

    # Check Python dependencies
    missing = []
    for mod in ["pypdf", "fitz"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append("pymupdf" if mod == "fitz" else mod)
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print(f"Install: pip install {' '.join(missing)}")
        sys.exit(1)

    # Auto-detect PDF type
    use_ocr = args.force_ocr or not is_text_based(str(input_path))

    if use_ocr:
        print("Image-based PDF detected. Using OCR...")
        if not ensure_tesseract():
            print("Error: Tesseract not found. See references/dependencies.md")
            sys.exit(1)
        headings = extract_headings_ocr(str(input_path), lang=args.lang)
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