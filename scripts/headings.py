"""Heading recognition, printed-TOC alignment and outline hierarchy."""

import re
import unicodedata


def clean_ocr_line(line, ocr_mode=False):
    line = unicodedata.normalize("NFKC", line)
    cleaned = re.sub(
        r"^[^\w\u4e00-\u9fff\d\u3000-\u303f\uff00-\uffef()]+", "", line
    ).strip()
    # Normalize spaces in "第 X 章" → "第X章"
    cleaned = re.sub(
        r"第\s*([一二三四五六七八九十百\d]+)\s*(单元|篇|部|章|节)", r"第\1\2", cleaned
    )
    cleaned = re.sub(r"附\s+录", "附录", cleaned)
    # Normalize "X .X" → "X.X"
    cleaned = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", cleaned)
    cleaned = re.sub(r"^(\d+(?:\.\d+){1,2})(?=[A-Za-z\u4e00-\u9fff])", r"\1 ", cleaned)
    cleaned = re.sub(r"^(\d+(?:\.\d+)+)\s*[“”「」\"]+\s*", r"\1 ", cleaned)
    cleaned = re.sub(r"^([一二三四五六七八九十]+)\s*、\s*", r"\1、", cleaned)
    cleaned = re.sub(r"^\(\s*([一二三四五六七八九十]+)\s*\)", r"(\1)", cleaned)
    if ocr_mode:
        cleaned = re.sub(r"([\u4e00-\u9fff])\s*([、，])\s*", r"\1\2", cleaned)
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
    if line.startswith("NATIVE_CHAPTER\t"):
        return {
            "type": "chapter",
            "title": clean_ocr_line(line.split("\t", 1)[1], True),
            "source": "native_vertical",
        }
    marker = re.match(r"^第[一二三四五六七八九十百\d]+(单元|篇|部|章|节)\s*", line)
    if marker:
        kind = {
            "单元": "part",
            "篇": "part",
            "部": "part",
            "章": "chapter",
            "节": "section",
        }[marker[1]]
        return {"type": kind, "title": line}
    if re.match(
        r"^(?:Chapter|Part)\s+(?:\d+|[IVXLCDM]+)\b|^Appendix\s+(?:\d+|[A-Z])\b",
        line,
        re.IGNORECASE,
    ):
        return {"type": "chapter", "title": line}
    if re.match(
        r"^附录(?:[一二三四五六七八九十百\d]+)?\s*[^。]{0,30}$|^后\s*记$", line
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
    if re.match(r"^[A-Z]\.\d+\.\d+\.?\s+\w+", line):
        return {"type": "subsection", "title": line}
    if re.match(r"^[A-Z]\.\d+\.?\s+\w+", line):
        return {"type": "section", "title": line}
    if re.match(r"^[A-Z]\.\s+[A-Z][A-Za-z].{0,60}$", line):
        return {"type": "chapter", "title": line}
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
    structural = {
        (
            h["page"],
            re.sub(
                r"\W",
                "",
                re.sub(
                    r"^第[一二三四五六七八九十百\d]+(?:单元|篇|部|章|节)\s*",
                    "",
                    clean_ocr_line(h["title"], True),
                ),
            ),
        )
        for h in headings
        if re.match(
            r"^第[一二三四五六七八九十百\d]+(?:单元|篇|部|章|节)",
            clean_ocr_line(h["title"], True),
        )
    }
    filtered = []
    seen_titles = set()
    chapter, section = None, None
    anchored_chapters = set()

    for h in sorted(headings, key=lambda h: h["page"]):
        title = h["title"]
        htype = h["type"]
        page = h["page"]

        if (
            not re.match(
                r"^第[一二三四五六七八九十百\d]+(?:单元|篇|部|章|节)",
                clean_ocr_line(title, True),
            )
            and (page, re.sub(r"\W", "", clean_ocr_line(title, True))) in structural
        ):
            continue
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

        # A numbered OCR header cannot move an already located native chapter.
        if htype == "chapter":
            normalized = clean_ocr_line(title, True)
            numbered = re.match(
                r"^第[一二三四五六七八九十百\d]+章|^(Chapter|Part|Appendix)\s+[A-Z\d]+",
                normalized,
                re.I,
            )
            root_key = re.sub(
                r"\W", "", normalized[numbered.end() :] if numbered else normalized
            ).lower()
            if re.match(r"^Part\b", normalized, re.I):
                anchored_chapters.clear()
            if h.get("source") == "native_vertical":
                anchored_chapters.add(root_key)
            elif numbered and root_key in anchored_chapters:
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
        if htype == "part":
            chapter, section = None, None
            anchored_chapters.clear()
        elif htype == "chapter":
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
    """Use semantic ranks; absent intermediate ranks do not create empty nodes."""
    tree, stack, numbered_sections = [], [], {}
    ranks = {"part": 0, "chapter": 1, "section": 2, "subsection": 3}
    for h in headings:
        rank = ranks[h["type"]]
        if re.match(r"^Part\s+[IVXLCDM\d]+\b", h["title"], re.I):
            rank = 0
        if re.match(
            r"^(?:Appendix|Preface|Index)\b|^(?:前言|序言|附录|后记)", h["title"], re.I
        ):
            stack.clear()
        while stack and stack[-1][1] >= rank:
            stack.pop()
        parent = stack[-1][0] if stack else -1
        if rank <= 1:
            numbered_sections.clear()
        number = re.match(r"^((?:\d+|[A-Z])\.\d+)\.\d+\.?\s", h["title"])
        if rank == 3 and number:
            parent = numbered_sections.get(number[1], parent)
        tree.append((h["page"], h["title"], parent))
        stack.append((len(tree) - 1, rank))
        number = re.match(r"^((?:\d+|[A-Z])\.\d+)\.?\s", h["title"])
        if rank == 2 and number:
            numbered_sections[number[1]] = len(tree) - 1
    return tree


def native_toc_rows(lines):
    """Pair native contents titles with separate left/right folios by geometry."""
    numbered = []
    titles = []
    inline = []
    for line in lines:
        title = clean_ocr_line("".join(span["text"] for span in line["spans"]), True)
        # A separator is mandatory: a title ending in a number is not a folio.
        trailing = re.fullmatch(
            r"(.+?)\s*(?:[-·.…]{3,}|(?:\.\s*){3,})\s*(\d{1,4})", title
        )
        leading = re.fullmatch(r"(\d{1,4})\s*/\s*(.+)", title)
        if trailing or leading:
            text, folio = (
                (trailing[1], trailing[2]) if trailing else (leading[2], leading[1])
            )
            if len(text) <= 60 and not re.search(r"[。！？]", text):
                inline.append((line["bbox"], text.strip(), int(folio)))
        if re.fullmatch(r"[0-9]{1,4}", title):
            numbered.append((line["bbox"], int(title)))
        elif re.match(
            r"^第[一二三四五六七八九十百\d]+(?:单元|篇|部|章|节)|^附录", title
        ):
            titles.append((line["bbox"], title))
    if (
        len(inline) >= 5
        and sum(bool(match_heading(title, True)) for _, title, _ in inline) >= 3
    ):
        return [
            f"[TOC]\t{title}\t{folio}"
            for _, title, folio in sorted(
                inline, key=lambda item: (item[0][1], item[0][0])
            )
        ]
    if len(titles) < 5 or len(numbered) < 5:
        return []
    rows = []
    for box, title in sorted(titles, key=lambda item: (item[0][1], item[0][0])):
        matches = [
            value
            for number_box, value in numbered
            if (number_box[2] <= box[0] or number_box[0] >= box[2])
            and abs((box[1] + box[3] - number_box[1] - number_box[3]) / 2)
            <= max(box[3] - box[1], number_box[3] - number_box[1]) * 0.4
        ]
        if len(matches) == 1:
            rows.append(f"[TOC]\t{title}\t{matches[0]}")
    return rows if len(rows) >= 5 else []


def headings_from_pages(pages, scanned, pdf_type="auto", visual=None, extended=False):
    from collections import Counter

    # Repeated marginal lines are page headers/footers, not chapter starts.
    def marginal_key(line):
        return re.sub(
            r"\s+\d+$", "", re.sub(r"^\d+\s+", "", clean_ocr_line(line, True))
        )

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
        if "[CONTENTS]" in lines or any(line.startswith("[TOC]\t") for line in lines):
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
                entry is None
                and pdf_type == "textbook"
                and raw_line in (visual or {}).get(number, [])
                and any(h["type"] == "chapter" for h in headings)
                and re.match(r"^[一二三四五六七八九十]+、", line)
            ):
                entry = match_heading(line, number in scanned, "auto")
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
                    and (
                        h.get("source") == "native_vertical"
                        or re.match(
                            r"^(?:Chapter|Part|Appendix)\b|^第.*章|^\d+\s",
                            h["title"],
                            re.I,
                        )
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
                    "source": "visual",
                }
            if entry:
                headings.append(dict(entry, page=number))
    toc_headings = align_printed_toc(pages)
    if toc_headings and pdf_type in {"auto", "textbook"}:
        # The printed outline has stronger structural evidence than running headers.
        # Preserve explicit structure outside its range, not generic visual labels.
        first, last = (
            min(h["page"] for h in toc_headings),
            max(h["page"] for h in toc_headings),
        )
        from bisect import bisect_right

        toc_keys = {(t["page"], clean_ocr_line(t["title"], True)) for t in toc_headings}
        toc_pages = [t["page"] for t in toc_headings]
        retained = []
        for heading in headings:
            page = heading["page"]
            if (page, clean_ocr_line(heading["title"], True)) in toc_keys:
                continue
            if extended and first <= page <= last:
                # Additional body titles are leaves, never replacement TOC parents.
                if (
                    heading["type"] in {"part", "chapter"}
                    and heading.get("source") != "visual"
                ):
                    continue
                parent = toc_headings[bisect_right(toc_pages, page) - 1]
                heading = dict(
                    heading,
                    type={
                        "part": "chapter",
                        "chapter": "section",
                        "section": "subsection",
                        "subsection": "subsection",
                    }[parent["type"]],
                )
            elif not (extended or heading.get("source") != "visual") or not (
                extended or heading["type"] == "part" or page < first or page > last
            ):
                continue
            retained.append(heading)
        headings = retained + toc_headings
        headings.sort(key=lambda h: (h["page"], h.get("source") != "printed_toc"))
    return filter_headings(headings, len(pages))


def align_printed_toc(pages):
    """Accept a printed-page offset only when independent body titles agree."""
    from collections import Counter

    def title_key(title):
        title = clean_ocr_line(title, True)
        title = re.sub(
            r"^第[一二三四五六七八九十百\d]+(?:单元|篇|部|章|节)\s*|^\d+(?:\.\d+)*\s*",
            "",
            title,
        )
        return re.sub(r"[\W_]", "", title).lower()

    entries, toc_pages, folio_votes, alternatives = [], set(), [], {}
    for page, text in pages:
        for line in text.splitlines():
            if line.startswith("[TOC_ALT]\t"):
                fields = line.split("\t")
                if len(fields) == 4:
                    _, primary, title, printed = fields
                else:
                    _, title, printed = fields
                    primary = ""
                alternatives.setdefault(
                    (int(printed), clean_ocr_line(primary, True)), []
                ).append(title)
            if line.startswith("[FOLIO]\t"):
                folio_votes.append((page, page - int(line.split("\t")[1])))
            if line.startswith("[TOC]\t"):
                _, title, printed = line.split("\t")
                entry = match_heading(title, True)
                # Unnumbered contents rows (labs, summaries, introductions) inherit
                # chapter context only after the page itself passed TOC validation.
                if entry is None and 2 <= len(title) <= 60:
                    entry = dict(
                        type="section"
                        if any(e["type"] == "chapter" for e in entries)
                        else "chapter",
                        title=title,
                    )
                if entry:
                    candidate = dict(entry, printed=int(printed))
                    if candidate not in entries:
                        entries.append(candidate)
                    toc_pages.add(page)
    if len(entries) < 5:
        return []

    def literal_key(title):
        return re.sub(r"\s+", "", clean_ocr_line(title, True)).casefold()

    candidates = {literal_key(e["title"]) for e in entries} | {
        literal_key(title) for choices in alternatives.values() for title in choices
    }
    locations, literal_locations = {}, {}
    for page, text in pages:
        if page in toc_pages:
            continue
        for line in text.splitlines():
            key = title_key(line)
            if len(key) >= 2 and not line.startswith("["):
                locations.setdefault(key, set()).add(page)
            literal = literal_key(line)
            if literal in candidates:
                literal_locations.setdefault(literal, set()).add(page)

    def marker_key(title):
        marker = re.match(
            r"^(?:\d+(?:\.\d+)*|第[一二三四五六七八九十百\d]+(?:单元|篇|部|章|节)|附录[一二三四五六七八九十百\d]+)",
            clean_ocr_line(title, True),
        )
        return marker[0] if marker else None

    def row_alternatives(entry):
        return alternatives.get(
            (entry["printed"], entry["title"]), []
        ) + alternatives.get((entry["printed"], ""), [])

    votes = []
    for entry in entries:
        choices = [entry["title"]] + row_alternatives(entry)
        offsets = set()
        for title in choices:
            hits = locations.get(title_key(title), set())
            if len(hits) == 1:
                offsets.add(next(iter(hits)) - entry["printed"])
        if len(offsets) == 1:
            votes.append(next(iter(offsets)))
    if not votes:
        return []
    offset, support = Counter(votes).most_common(1)[0]
    title_support = support >= 3 and support / len(votes) >= 0.75
    folio_votes = [vote for page, vote in folio_votes if page not in toc_pages]
    folio_offset, folio_count = (
        Counter(folio_votes).most_common(1)[0] if folio_votes else (None, 0)
    )
    folio_support = (
        folio_count >= 10
        and folio_count / len(folio_votes) >= 0.9
        and folio_offset in votes
    )
    if not title_support and not folio_support:
        return []
    if not title_support:
        offset = folio_offset
    for entry in entries:
        choices = [
            title
            for title in row_alternatives(entry)
            if entry["printed"] + offset
            in literal_locations.get(literal_key(title), set())
            or (
                marker_key(title)
                and marker_key(title) == marker_key(entry["title"])
                and entry["printed"] + offset in locations.get(title_key(title), set())
            )
        ]
        if (
            entry["printed"] + offset
            not in locations.get(title_key(entry["title"]), set())
            and len(set(choices)) == 1
        ):
            confirmed = match_heading(choices[0], True)
            if confirmed and confirmed["type"] == entry["type"]:
                entry["title"] = choices[0]
    # An isolated pagination inversion is evidence of an OCR error, not a new offset.
    entries = [
        e
        for i, e in enumerate(entries)
        if not (
            0 < i < len(entries) - 1
            and entries[i - 1]["printed"] <= entries[i + 1]["printed"]
            and not entries[i - 1]["printed"]
            <= e["printed"]
            <= entries[i + 1]["printed"]
        )
    ]
    resolved = [
        dict(
            type=e["type"],
            title=e["title"],
            page=e["printed"] + offset,
            source="printed_toc",
        )
        for e in entries
    ]
    if any(
        not 1 <= e["page"] <= len(pages) or e["page"] in toc_pages for e in resolved
    ):
        return []
    if any(a["page"] > b["page"] for a, b in zip(resolved, resolved[1:], strict=False)):
        return []
    return resolved


def diagnose_outline(headings, pages):
    """Expose evidence conflicts without claiming a validated confidence score."""
    diagnostics, seen, parent = [], {}, None
    for h in headings:
        title = clean_ocr_line(h["title"], True)
        marker = re.match(r"^第[一二三四五六七八九十百\d]+(单元|篇|部|章|节)", title)
        if h["type"] == "part":
            seen.clear()
            parent = None
        if marker and marker.end() == len(title):
            diagnostics.append(
                dict(
                    code="fragmented_heading",
                    message=f"Heading marker has no title: {title} (PDF page {h['page']}).",
                    pages=[h["page"]],
                )
            )
        if marker and h["type"] in {"chapter", "part"}:
            key = re.sub(r"\W", "", title)
            if key in seen and seen[key] != h["page"]:
                diagnostics.append(
                    dict(
                        code="suspected_running_header",
                        message=f"Repeated structural title: {title} (PDF pages {seen[key]}, {h['page']}).",
                        pages=[seen[key], h["page"]],
                    )
                )
            seen[key] = h["page"]
        if h["type"] == "chapter":
            parent = h
        section_number = re.match(r"^(\d+)\.\d+\s", title)
        chapter_number = (
            re.match(r"^第(\d+)章|^Chapter\s+(\d+)\b", parent["title"], re.I)
            if parent
            else None
        )
        if (
            section_number
            and chapter_number
            and section_number[1]
            != next(group for group in chapter_number.groups() if group is not None)
        ):
            diagnostics.append(
                dict(
                    code="hierarchy_conflict",
                    message=f"Section numbering conflicts with its chapter: {title} (PDF page {h['page']}).",
                    pages=[parent["page"], h["page"]],
                )
            )
        if marker and h["type"] == "section" and parent is None:
            diagnostics.append(
                dict(
                    code="missing_chapter_parent",
                    message=f"Section has no preceding chapter: {title} (PDF page {h['page']}).",
                    pages=[h["page"]],
                )
            )
    if any("[TOC]\t" in text for _, text in pages) and not any(
        h.get("source") == "printed_toc" for h in headings
    ):
        diagnostics.append(
            dict(
                code="unconfirmed_pagination",
                message="Printed contents page destinations could not be corroborated; review page offsets.",
                pages=[n for n, text in pages if "[TOC]\t" in text],
            )
        )
    unreadable = sum(
        int(line.split("\t")[1])
        for _, text in pages
        for line in text.splitlines()
        if line.startswith("[TOC_REVIEW]\t")
    )
    if unreadable:
        diagnostics.append(
            dict(
                code="incomplete_printed_toc",
                message=f"Printed contents has {unreadable} unreadable rows; inferred hierarchy may omit parents or children.",
                pages=[n for n, text in pages if "[TOC_REVIEW]\t" in text],
            )
        )
    return diagnostics
