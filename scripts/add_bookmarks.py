#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path

from headings import (  # noqa: F401 - preserve the importable script API
    align_printed_toc,
    build_tree_from_entries,
    build_tree_from_headings,
    clean_ocr_line,
    filter_headings,
    headings_from_pages,
    match_heading,
    parse_toc_file,
)
from ocr import _read_image_page

VERSION = "0.3.0"


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


def publish_file(temporary, destination, overwrite=False):
    """Publish a completed file; an exclusive link prevents overwrite races."""
    if overwrite:
        os.replace(temporary, destination)
    else:
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise FileExistsError(
                f"Output exists: {destination}; use --overwrite"
            ) from error
        os.unlink(temporary)


def page_needs_ocr(page):
    """Detect image-dominated pages, including inline images and text watermarks."""
    blocks = page.get_text("blocks")
    text = "".join(b[4] for b in blocks if b[6] == 0)
    area = page.rect.get_area()
    images = page.get_image_info()
    image_area = min(area, sum(fitz_rect_area(i["bbox"], page.rect) for i in images))
    text_area = sum(fitz_rect_area(b[:4], page.rect) for b in blocks if b[6] == 0)
    useful = sum(c.isalnum() for c in text)
    return bool(images) and (
        useful < 40 or (image_area / area > 0.65 and text_area / area < 0.2)
    )


def fitz_rect_area(box, bounds):
    import fitz

    return max(0, (fitz.Rect(box) & bounds).get_area())


def add_bookmarks(
    pdf_path, tree, output_path, verification="structural", overwrite=False
):
    if Path(pdf_path).resolve() == Path(output_path).resolve():
        raise ValueError("Output must differ from input PDF")
    if Path(output_path).exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output_path}; use --overwrite")
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
    doc.set_pagemode("UseOutlines")
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
        publish_file(temporary, output_path, overwrite)
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
        scanned = [i for i, page in enumerate(doc) if force_ocr or page_needs_ocr(page)]
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


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(
        description="Add hierarchical bookmarks to PDF files"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("input")
    parser.add_argument("-o", "--output")
    parser.add_argument("--lang", default="chi_sim+eng")
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing outputs explicitly"
    )
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
        "review_required": False,
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
    toc_path = (
        Path(args.output)
        if args.analyze and args.output
        else source.with_name(source.stem + "_suggested_toc.txt")
    )
    destinations = [toc_path] if args.analyze else [output]
    if args.generate_toc:
        destinations.append(toc_path)
    for destination in destinations:
        if destination.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {destination}; use --overwrite")
    if args.toc:
        if not Path(args.toc).is_file():
            raise ValueError(f"TOC file not found: {args.toc}")
        result["quality"] = "provided_toc"
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
        toc_signals = [
            line.split("\t")
            for _, text in pages
            for line in text.splitlines()
            if line.startswith("[TOC_REVIEW]\t")
        ]
        unreadable = sum(int(signal[1]) for signal in toc_signals)
        uncertain = sum(int(signal[2]) for signal in toc_signals)
        if unreadable or uncertain:
            warnings.append(
                f"Printed TOC has {unreadable} unreadable candidate rows and {uncertain} low-confidence titles; review the suggested outline for omissions and OCR errors."
            )
        if (
            scanned
            and any("[TOC]\t" in text for _, text in pages)
            and not any(h.get("source") == "printed_toc" for h in headings)
        ):
            warnings.append(
                "Printed TOC pagination could not be corroborated; using body candidates. Review page destinations."
            )
        if scanned:
            warnings.append(
                "OCR headings are unverified; review titles, hierarchy and page destinations with --analyze before use."
            )
        if len(pages) >= 50 and len(headings) < max(3, len(pages) // 40):
            warnings.append(
                "Few heading candidates for this document; the outline may be incomplete."
            )
        blank = sum(not text.strip() for number, text in pages if number in scanned)
        if blank:
            warnings.append(
                f"OCR returned no text on {blank} pages; these may be blank or unreadable."
            )
        result.update(
            recognition_method="printed_toc"
            if any(h.get("source") == "printed_toc" for h in headings)
            else "body_headings",
            review_required=bool(warnings),
            quality="unverified",
            candidates=len(headings),
        )
        for warning in warnings:
            print("Warning: " + warning)
        print(f"Heading profile: {args.type}")
        if args.analyze or args.generate_toc:
            levels, rows = {}, []
            for index, (page, title, parent) in enumerate(
                build_tree_from_headings(headings)
            ):
                levels[index] = levels[parent] + 1 if parent >= 0 else 0
                rows.append("  " * levels[index] + f"{title}\t{page}\n")
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=toc_path.parent, delete=False
            ) as handle:
                temporary = handle.name
                handle.write("".join(rows))
            try:
                publish_file(temporary, toc_path, args.overwrite)
            finally:
                Path(temporary).unlink(missing_ok=True)
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
    count = add_bookmarks(
        str(source), tree, str(output), args.verify, overwrite=args.overwrite
    )
    result.update(bookmarks=count, output=str(output), verification=args.verify)
    if not args.json:
        print(
            f"Added {count} bookmarks.\nContent verified ({args.verify}).\nOutput: {output}"
        )
    return result


if __name__ == "__main__":
    sys.exit(main())
