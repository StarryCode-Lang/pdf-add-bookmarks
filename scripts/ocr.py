"""Small, optional OCR layout helpers using the existing Pillow/Tesseract stack."""

import os
import re

from headings import clean_ocr_line, match_heading


def remove_solid_leaders(image):
    """Erase thin horizontal TOC leaders while retaining glyphs and colour bands."""
    from PIL import ImageDraw, ImageOps

    gray = ImageOps.grayscale(image)
    segments, groups = {}, []
    for y in range(image.height):
        start = None
        for x, pixel in enumerate(
            gray.crop((0, y, image.width, y + 1)).tobytes() + b"\xff"
        ):
            if pixel < 205 and start is None:
                start = x
            if pixel >= 205 and start is not None:
                if x - start >= max(25, image.width * 0.22):
                    segments.setdefault(y, []).append((start, x))
                start = None
    for y in sorted(segments):
        if not groups or y != groups[-1][-1] + 1:
            groups.append([])
        groups[-1].append(y)
    result = image.copy()
    draw = ImageDraw.Draw(result)
    for group in groups:
        if len(group) <= 6:
            for y in group:
                for begin, end in segments[y]:
                    draw.line((begin, y, end - 1, y), fill="white")
    return result


def read_toc_rows(image, data, lang, total_pages):
    """Read a detected printed TOC row by row, separating dotted leaders and folios.

    Returns OCR evidence, never an inferred or hardcoded document page offset.
    """
    from statistics import median

    import pytesseract
    from PIL import ImageChops, ImageOps

    words = [i for i, text in enumerate(data["text"]) if text.strip()]
    prefixes = [
        i for i in words if re.fullmatch(r"\d+\.\d+", data["text"][i].strip("*. "))
    ]
    folios = [
        i
        for i in words
        if re.fullmatch(r"\d{1,4}", data["text"][i].strip())
        and data["left"][i] > image.width * 0.65
    ]
    if len(prefixes) < 5 and not (len(prefixes) >= 2 and len(folios) >= 3):
        return []
    # A TOC has numbered titles paired with aligned folios, not just decimal values.
    # This avoids expensive crop OCR on mathematical exercise tables.
    paired = []
    for prefix in prefixes:
        center = data["top"][prefix] + data["height"][prefix] / 2
        for folio in folios:
            folio_center = data["top"][folio] + data["height"][folio] / 2
            tolerance = max(data["height"][prefix], data["height"][folio]) * 1.2
            if abs(center - folio_center) > tolerance:
                continue
            if any(
                data["left"][prefix] + data["width"][prefix]
                <= data["left"][word]
                < data["left"][folio]
                and abs(data["top"][word] + data["height"][word] / 2 - center)
                <= tolerance
                and re.search(r"[\u4e00-\u9fff]", data["text"][word])
                and float(data["conf"][word]) >= 40
                for word in words
            ):
                paired.append(
                    (data["left"][prefix], data["left"][folio] + data["width"][folio])
                )
    required = 3 if len(prefixes) >= 5 else 2
    if not any(
        sum(
            abs(left - other_left) < image.width * 0.05
            and abs(right - other_right) < image.width * 0.02
            for other_left, other_right in paired
        )
        >= required
        for left, right in paired
    ):
        return []
    positions = sorted(data["left"][i] for i in prefixes)
    gaps = [(b - a, b) for a, b in zip(positions, positions[1:], strict=False)]
    gap, second_column = max(gaps, default=(0, 0))
    if gap > image.width * 0.2:
        boundary = int(second_column - image.width * 0.035)
        if (
            sum(x < boundary for x in positions) >= 3
            and sum(x >= boundary for x in positions) >= 3
        ):
            rows = []
            for begin, end in ((0, boundary), (boundary, image.width)):
                indices = [
                    i
                    for i in words
                    if begin <= data["left"][i] + data["width"][i] / 2 < end
                ]
                column = {
                    key: [values[i] for i in indices] for key, values in data.items()
                }
                column["left"] = [x - begin for x in column["left"]]
                rows.extend(
                    read_toc_rows(
                        image.crop((begin, 0, end, image.height)),
                        column,
                        lang,
                        total_pages,
                    )
                )
            return rows
    left = max(0, min(data["left"][i] for i in prefixes) - image.width * 0.035)
    right = max(
        (data["left"][i] + data["width"][i] for i in folios), default=image.width * 0.9
    )
    number_left = (
        min(
            (data["left"][i] for i in folios if data["width"][i] < image.width * 0.06),
            default=right - image.width * 0.035,
        )
        - 8
    )
    gray = ImageOps.grayscale(image)
    bands = []
    for y in range(int(image.height * 0.08), int(image.height * 0.95)):
        dark = sum(gray.crop((int(left), y, int(right), y + 1)).histogram()[:150])
        if dark <= image.width * 0.012:
            continue
        if not bands or y - bands[-1][1] > max(4, image.height * 0.003):
            bands.append([y, y])
        else:
            bands[-1][1] = y
    bands = [(a, b + 1) for a, b in bands if 7 <= b + 1 - a <= image.height * 0.07]
    if len(bands) > 80:
        return []  # Noisy backgrounds are unsuitable for this layout pass.
    merged, i = [], 0
    while i < len(bands):
        top, bottom = bands[i]
        numbered = any(
            top <= data["top"][j] + data["height"][j] / 2 <= bottom for j in prefixes
        )
        same_folio = any(
            top <= data["top"][j] + data["height"][j] / 2 <= bottom for j in folios
        )
        if numbered and not same_folio and i + 1 < len(bands):
            next_top, next_bottom = bands[i + 1]
            next_prefix = any(
                next_top <= data["top"][j] + data["height"][j] / 2 <= next_bottom
                for j in prefixes
            )
            next_folio = any(
                next_top <= data["top"][j] + data["height"][j] / 2 <= next_bottom
                for j in folios
            )
            if (
                not next_prefix
                and next_folio
                and next_top - bottom < (bottom - top) * 1.5
            ):
                bottom = next_bottom
                i += 1
        merged.append((top, bottom))
        i += 1
    entries, failed, uncertain = [], 0, 0
    for top, bottom in merged:
        crop = image.crop((int(left), top - 5, int(number_left), bottom + 5))
        crop = remove_solid_leaders(crop)
        red, green, blue = crop.split()
        # Remove saturated colour backgrounds without a new imaging dependency.
        clean = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(
            lambda pixel: 255 if pixel > 180 else 0
        )
        runs, start = [], None
        for x in range(clean.width):
            active = clean.crop((x, 0, x + 1, clean.height)).getextrema()[0] < 150
            if active and start is None:
                start = x
            if not active and start is not None:
                runs.append((start, x))
                start = None
        chain, leader = [], None
        for begin, end in runs:
            if end - begin <= max(6, clean.height * 0.22):
                chain.append((begin, end))
                if len(chain) >= 6:
                    leader = chain[0][0]
                    break
            else:
                chain = []
        if leader:
            crop = crop.crop((0, 0, leader, crop.height))
            clean = clean.crop((0, 0, leader, clean.height))
        alternatives = []
        title_languages = [lang]
        if "chi_sim" in lang.split("+") and lang != "chi_sim":
            title_languages.append("chi_sim")
        for sample, title_language in (
            (sample, language)
            for language in title_languages
            for sample in (crop, clean)
        ):
            result = pytesseract.image_to_data(
                sample,
                lang=title_language,
                config="--psm 6"
                if bottom - top > median(b - a for a, b in bands) * 2.2
                else "--psm 7",
                timeout=120,
                output_type=pytesseract.Output.DICT,
            )
            valid = [i for i, word in enumerate(result["text"]) if word.strip()]
            title = clean_ocr_line(
                " ".join(result["text"][i] for i in valid), True
            ).rstrip(" _|.-")
            confidence = sum(max(0, float(result["conf"][i])) for i in valid) / max(
                1, len(valid)
            )
            alternatives.append((title, confidence))
        if not any(
            re.search(r"第[一二三四五六七八九十\d]+章", title)
            for title, _ in alternatives
        ):
            if bottom - top > median(b - a for a, b in bands) * 1.3:
                prefix_crop = image.crop(
                    (
                        int(left),
                        top - 5,
                        int(left + (number_left - left) * 0.32),
                        bottom + 5,
                    )
                )
                prefix = clean_ocr_line(
                    pytesseract.image_to_string(
                        prefix_crop, lang=lang, config="--psm 7", timeout=120
                    ),
                    True,
                )
                chapter_prefix = re.search(r"第[一二三四五六七八九十\d]+章", prefix)
                plain = alternatives[1][0]
                if chapter_prefix and re.fullmatch(r"[\u4e00-\u9fff]{2,30}", plain):
                    alternatives.append((chapter_prefix[0] + plain, alternatives[1][1]))
        chapter = re.match(r"^(第[一二三四五六七八九十\d]+章)", alternatives[0][0])
        if chapter and not re.match(r"^第.*章", alternatives[1][0]):
            alternatives[1] = (chapter[1] + alternatives[1][0], alternatives[1][1])
        valid = [
            (title, confidence)
            for title, confidence in alternatives
            if (
                re.match(r"^第[一二三四五六七八九十\d]+章", title)
                or re.match(r"^\d+\.\d+\s", title)
            )
            and not re.fullmatch(r"第[一二三四五六七八九十\d]+章", title)
            and match_heading(title, True)
            and re.search(r"[\u4e00-\u9fff]", title)
        ]
        if not valid:
            failed += any(
                top <= data["top"][j] + data["height"][j] / 2 <= bottom
                for j in prefixes
            )
            continue

        def candidate_score(pair):
            suffix = re.sub(r"^第[一二三四五六七八九十\d]+章|^\d+\.\d+", "", pair[0])
            return (sum("\u4e00" <= c <= "\u9fff" for c in suffix) >= 2, pair[1])

        title, confidence = max(valid, key=candidate_score)
        number_crop = ImageOps.expand(
            remove_solid_leaders(
                image.crop(
                    (
                        int(number_left),
                        top - 6,
                        min(image.width, int(right + image.width * 0.025)),
                        bottom + 6,
                    )
                )
            ),
            16,
            "white",
        )
        number = (
            pytesseract.image_to_string(
                number_crop,
                lang="eng" if "eng" in lang.split("+") else lang,
                config="--psm 7",
                timeout=120,
            )
            .strip()
            .strip(".· ")
        )
        if not number.isdigit() and re.match(r"^第.*章", title):
            below = {
                data["text"][i]
                for i in folios
                if bottom
                <= data["top"][i]
                <= bottom + median(b - a for a, b in bands) * 2 + 12
                and float(data["conf"][i]) >= 40
            }
            if len(below) == 1:
                number = next(iter(below))
        match = re.fullmatch(r"[\W_]*(\d{1,4})[\W_]*", number)
        number = match[1] if match else ""
        if number.isdigit() and 0 < int(number) <= total_pages:
            entries.append(f"[TOC]\t{title}\t{int(number)}")
            uncertain += confidence < 60
        else:
            failed += 1
    if failed or uncertain:
        entries.append(f"[TOC_REVIEW]\t{failed}\t{uncertain}")
    return entries


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
        total_pages = len(doc)
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
    folios = {
        int(data["text"][i])
        for i in range(len(data["text"]))
        if re.fullmatch(r"\d{1,4}", data["text"][i].strip())
        and data["top"][i] > image.height * 0.9
        and (data["left"][i] < image.width * 0.3 or data["left"][i] > image.width * 0.7)
        and float(data["conf"][i]) >= 40
        and 0 < int(data["text"][i]) <= total_pages
    }
    text_lines, titles = [], []
    for indices in lines.values():
        line = " ".join(data["text"][i] for i in indices)
        top = min(data["top"][i] for i in indices)
        if top < image.height * 0.06 or top > image.height * 0.96:
            continue
        text_lines.append(line)
        if (
            image.height * 0.06 < top < image.height * 0.9
            and baseline
            and median(data["height"][i] for i in indices)
            >= baseline * (1.2 if extended else 1.4)
            and 3 <= len(line) <= 100
            and (len(indices) >= 2 or len(line) >= 5)
            and not re.search(r"[。！？!?]|[.!]$", line)
        ):
            titles.append(line)
    toc_rows = read_toc_rows(image, data, lang, total_pages) if "chi" in lang else []
    # Dense mathematical formulae can make automatic segmentation lose exam headers.
    if "chi" in lang and any(
        re.search(r"选择题|填空题|解答题", clean_ocr_line(line, True))
        for line in text_lines
    ):
        header_text = pytesseract.image_to_string(
            image.crop((0, 0, image.width, int(image.height * 0.45))),
            lang=lang,
            config="--psm 6",
            timeout=120,
        )
        text_lines.extend(
            line.strip()
            for line in header_text.splitlines()
            if re.match(
                r"^[一二三四五六七八九十]+、(?:选择题|填空题|解答题)",
                clean_ocr_line(line, True),
            )
        )
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
    folio_rows = [f"[FOLIO]\t{next(iter(folios))}"] if len(folios) == 1 else []
    return index + 1, "\n".join(merged + toc_rows + folio_rows), titles
