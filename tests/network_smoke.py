"""Optional real-document benchmark: pinned sources, independent labels, local evidence."""

import hashlib
import inspect
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import add_bookmarks as app  # noqa: E402

TEXTBOOK = "https://raw.githubusercontent.com/TapXWorld/ChinaTextbook/master/"
SOURCES = {
    "text": (
        "https://greenteapress.com/thinkpython2/thinkpython2.pdf",
        "6033000bac3f9268ad75ee041bf8e5d9a3bc8a33bb156399cbd014918cb59f94",
        "eng",
        "auto",
    ),
    "scan": (
        "https://archive.org/download/CalculusMadeEasy/Calculus_Made_Easy_Thompson.pdf",
        "a3fb238d8710d78306ab99435ed8aa0c5353586dd69725ebe690bcfecdeb985b",
        "eng",
        "auto",
    ),
    "zh-text": (
        TEXTBOOK
        + urllib.parse.quote(
            "初中/数学/人教版-人民教育出版社/七年级/义务教育教科书·数学七年级上册.pdf"
        ),
        "cb14b1c61bc4f85e42f714073f67eedd9cfeaacc28bc663b3d68b19b4e8df58a",
        "chi_sim+eng",
        "textbook",
    ),
    "zh-scan": (
        TEXTBOOK
        + urllib.parse.quote(
            "初中/数学/北京版-北京出版社/七年级/义务教育教科书·数学七年级上册.pdf"
        ),
        "0b5a395273f0d867e58776d74c69970461b9cf79933025f5f547d03e0abff280",
        "chi_sim+eng",
        "textbook",
    ),
    "zh-exam": (
        "https://imgs.app.gaokaozhitongche.com/resource/pdf/paper/202506/20250617081036_lTiMG1.pdf",
        "2ca7d17a6c493fe56b95f6db214b1eeba5817cdcd4520ae43ff90fc69fcd59e7",
        "chi_sim+eng",
        "exam",
    ),
}
# Labels transcribed from printed contents before running recognition. Page numbers are PDF pages.
SCAN_CHAPTER_PAGES = [
    15,
    17,
    23,
    32,
    40,
    49,
    63,
    66,
    81,
    90,
    107,
    126,
    135,
    148,
    179,
    189,
    196,
    205,
    220,
    240,
    248,
    263,
    280,
]
ZH_TEXT = [
    (1, "第一章 有理数", 8),
    (2, "1.1 正数和负数", 9),
    (2, "1.2 有理数", 13),
    (2, "1.3 有理数的加减法", 23),
    (2, "1.4 有理数的乘除法", 35),
    (2, "1.5 有理数的乘方", 48),
    (1, "第二章 整式的加减", 60),
    (2, "2.1 整式", 61),
    (2, "2.2 整式的加减", 69),
    (1, "第三章 一元一次方程", 84),
    (2, "3.1 从算式到方程", 85),
    (2, "3.2 解一元一次方程（一）", 93),
    (2, "3.3 解一元一次方程（二）", 100),
    (2, "3.4 实际问题与一元一次方程", 107),
    (1, "第四章 几何图形初步", 120),
    (2, "4.1 几何图形", 121),
    (2, "4.2 直线、射线、线段", 132),
    (2, "4.3 角", 139),
    (2, "4.4 课题学习", 149),
]
ZH_SCAN = [
    (1, "第一章 有理数", 7),
    (2, "1.1 负数的引入", 8),
    (2, "1.2 用数轴上的点表示有理数", 11),
    (2, "1.3 相反数和绝对值", 14),
    (2, "1.4 有理数的加法", 23),
    (2, "1.5 有理数的减法", 29),
    (2, "1.6 有理数加减法的混合运算", 32),
    (2, "1.7 有理数的乘法", 42),
    (2, "1.8 有理数的除法", 47),
    (2, "1.9 有理数的乘方", 51),
    (2, "1.10 有理数的混合运算", 56),
    (2, "1.11 数的近似和科学记数法", 60),
    (2, "1.12 用计算器做有理数的混合运算", 63),
    (1, "第二章 一元一次方程", 75),
    (2, "2.1 字母表示数", 76),
    (2, "2.2 同类项与合并同类项", 82),
    (2, "2.3 算式与等式", 86),
    (2, "2.4 等式的基本性质", 89),
    (2, "2.5 一元一次方程", 94),
    (2, "2.6 列方程解应用问题", 107),
    (1, "第三章 简单的几何图形", 125),
    (2, "3.1 平面图形与立体图形", 126),
    (2, "3.2 某些立体图形的展开图", 127),
    (2, "3.3 从不同方向观察立体图形", 128),
    (2, "3.4 点、线、面、体", 131),
    (2, "3.5 直线、射线、线段", 133),
    (2, "3.6 角及其分类", 141),
    (2, "3.7 角的度量与角的换算", 144),
    (2, "3.8 角平分线", 146),
    (2, "3.9 两条直线的位置关系", 149),
    (2, "3.10 相交线与平行线", 150),
    (2, "3.11 用计算机绘图", 154),
]
ZH_EXAM = [
    (2, "一、选择题", 1),
    (2, "二、选择题", 2),
    (2, "三、填空题", 2),
    (2, "四、解答题", 2),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(title):
    title = unicodedata.normalize("NFKC", title)
    title = re.sub(
        r"^(Chapter|Part|Appendix)\s+(\d+|[A-Z]+)\.?\s+|^\d+(?:\.\d+)*\.?\s+|^[A-Z]\.\d+\s+",
        "",
        title,
        flags=re.I,
    )
    return re.sub(r"\W", "", title).lower()


def score(reference, candidates):
    expected = {(level, normalize(title), page) for level, title, page in reference}
    actual = {(level, normalize(title), page) for level, title, page in candidates}
    matched = len(expected & actual)
    return dict(
        reference_entries=len(expected),
        scored_candidates=len(actual),
        exact_matches=matched,
        precision=matched / len(actual) if actual else 0,
        recall=matched / len(expected),
        missing=sorted(expected - actual),
        unexpected=sorted(actual - expected),
    )


def download(url, source, expected_hash):
    if not source.exists():
        with (
            urllib.request.urlopen(url, timeout=120) as response,
            source.open("wb") as file,
        ):
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 64 * 1024 * 1024:
                    raise ValueError("Sample exceeds 64 MiB")
                file.write(chunk)
    if digest(source) != expected_hash:
        raise ValueError(
            "Source changed; review labels before changing its pinned hash"
        )


def main():
    directory = ROOT / "validation"
    directory.mkdir(exist_ok=True)
    selected = sys.argv[1:] or list(SOURCES) + ["zh-low"]
    extraction_hash = hashlib.sha256(
        (
            inspect.getsource(app.read_pages) + inspect.getsource(app._read_image_page)
        ).encode()
    ).hexdigest()
    rows = []
    for name in selected:
        base = "zh-scan" if name == "zh-low" else name
        url, expected_hash, lang, profile = SOURCES[base]
        original = directory / (base + "-original.pdf")
        download(url, original, expected_hash)
        source = directory / (name + ".pdf")
        with fitz.open(original) as doc:
            reference = doc.get_toc()
            assert len(doc) >= (10 if base == "zh-exam" else 100)
            original_outlines = len(reference)
            if not source.exists():
                if name == "zh-low":
                    # Deliberately degraded derivative, not a second independent book.
                    with fitz.open() as degraded:
                        for page in doc:
                            pix = page.get_pixmap(dpi=100, colorspace=fitz.csGRAY)
                            target = degraded.new_page(
                                width=page.rect.width, height=page.rect.height
                            )
                            target.insert_image(
                                target.rect, stream=pix.tobytes("jpeg", jpg_quality=30)
                            )
                        degraded.save(source)
                elif reference:
                    doc.set_toc([])
                    doc.save(source)
                else:
                    source.write_bytes(original.read_bytes())
        with fitz.open(source) as doc:
            assert not doc.get_toc()
        if name != "zh-low":
            assert app.verify_content(original, source), (
                "Prepared input changed page content"
            )
        key = extraction_hash + digest(source) + lang
        cache = directory / (name + "-pages.json")
        cached = json.loads(cache.read_text()) if cache.exists() else {}
        if cached.get("key") == key:
            pages, scanned = cached["pages"], set(cached["scanned"])
            visual = {int(k): v for k, v in cached["visual"].items()}
            seconds = cached["recognition_seconds"]
        else:
            started = time.perf_counter()
            pages, scanned, visual = app.read_pages(
                str(source), lang=lang, workers=4, dpi=200
            )
            seconds = time.perf_counter() - started
            cache.write_text(
                json.dumps(
                    dict(
                        key=key,
                        pages=pages,
                        scanned=sorted(scanned),
                        visual=visual,
                        recognition_seconds=seconds,
                    )
                ),
                encoding="utf-8",
            )
        headings = app.headings_from_pages(
            pages, scanned, pdf_type=profile, visual=visual
        )
        output = directory / (name + "_with_bookmarks.pdf")
        started = time.perf_counter()
        if headings:
            app.add_bookmarks(
                source, app.build_tree_from_headings(headings), output, "full"
            )
            with fitz.open(output) as doc:
                toc = doc.get_toc()
        else:
            toc = []
        if name == "text":
            metrics = score(reference, toc)
            assert not metrics["missing"], metrics["missing"]
            metrics["reference_match_fraction"] = metrics.pop("precision")
            metrics["additional_candidates"] = metrics.pop("unexpected")
            scope = "Publisher outline; additional visual titles are unlabelled"
        elif name == "scan":
            found = {
                h["page"]
                for h in headings
                if re.match(r"^CHAPTER\s+[A-Z]+\b", h["title"], re.I)
            }
            assert found == set(SCAN_CHAPTER_PAGES), found
            metrics = dict(
                reference_chapters=23,
                correct_chapter_pages=len(found),
                chapter_page_recall=1.0,
            )
            scope = "Chapter destination pages only; OCR wording and extra titles are unlabelled"
        else:
            labels = (
                ZH_EXAM
                if base == "zh-exam"
                else ZH_TEXT
                if base == "zh-text"
                else ZH_SCAN
            )
            candidates = [
                row
                for row in toc
                if (row[0] <= 2 and not re.match(r"^\d+\.", row[1]))
                and (
                    normalize(row[1])
                    in {normalize(title) for _level, title, _page in labels}
                )
                or (
                    re.match(r"^[一二三四五六七八九十]+、", row[1])
                    if base == "zh-exam"
                    else re.match(r"^第.*章|^\d+\.\d+\s", row[1])
                )
            ]
            metrics = score(labels, candidates)
            metrics["unscored_candidates"] = len(toc) - len(candidates)
            scope = "Manual chapter/numbered-section labels only, or the four question-type headers; not every visual candidate"
            # Reviewed TOC is the documented fallback, independent of automatic recognition.
            reviewed = directory / (name + "-reviewed.pdf")
            reviewed_labels = (
                labels
                if labels[0][0] == 1
                else [(1, "2025年普通高等学校招生全国统一考试（新I卷数学）", 1)]
                + labels
            )
            app.add_bookmarks(
                source,
                app.build_tree_from_entries(
                    [
                        dict(title=t, page=p, level=level - 1)
                        for level, t, p in reviewed_labels
                    ]
                ),
                reviewed,
                "full",
            )
            with fitz.open(reviewed) as doc:
                assert doc.get_toc() == [list(row) for row in reviewed_labels]
        row = dict(
            name=name,
            url=url,
            original_sha256=digest(original),
            input_sha256=digest(source),
            pages=len(pages),
            original_outline_count=original_outlines,
            input_outline_count=0,
            ocr_pages=len(scanned),
            bookmarks=len(toc),
            recognition_seconds=round(seconds, 2),
            save_and_verify_seconds=round(time.perf_counter() - started, 2),
            automatic_content_preserved=bool(toc),
            reviewed_toc_verified=base.startswith("zh"),
            derived_low_quality=name == "zh-low",
            scope=scope,
            metrics=metrics,
            toc=toc,
        )
        rows.append(row)
        print(
            json.dumps({k: v for k, v in row.items() if k != "toc"}, ensure_ascii=True),
            flush=True,
        )
    results = dict(
        version=app.VERSION,
        python=sys.version,
        pymupdf=fitz.VersionBind,
        tesseract=str(__import__("pytesseract").get_tesseract_version()),
        implementation_sha256=digest(ROOT / "scripts/add_bookmarks.py"),
        results=rows,
    )
    (directory / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
