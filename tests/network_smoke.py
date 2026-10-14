"""Optional real-document benchmark: pinned sources, independent labels, local evidence."""

import hashlib
import importlib.metadata
import inspect
import json
import re
import subprocess
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
    "zh-independent": (
        TEXTBOOK
        + urllib.parse.quote(
            "初中/数学/冀教版-河北教育出版社/八年级/义务教育教科书·数学八年级上册.pdf"
        ),
        "972482f9736a60c5db028def52b2efa0eff10802bfde02af4d70582bf419d5b1",
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
# Selected after freezing v0.3.1 recognition; never used to tune this release.
SOURCES["blind-java"] = (
    "https://greenteapress.com/thinkjava7/thinkjava2.pdf",
    "b1fec11a9d39765bb23a73d94452e7c8caf50a165034543eb1efceba1fd8a68e",
    "eng",
    "auto",
)
SOURCES["zh-blind-physics"] = (
    TEXTBOOK
    + urllib.parse.quote(
        "初中/物理/教科版-教育科学出版社/八年级/义务教育教科书·物理八年级上册.pdf"
    ),
    "1583dbe84c0dc28a70dd55ccc77206a1a5580639f378b102d599fa9d8f35edb2",
    "chi_sim+eng",
    "textbook",
)
# Six chapter labels from printed contents; +7 offset checked against body pages.
ZH_BLIND_PHYSICS = [
    (1, "第一章 走进实验室", 12),
    (1, "第二章 运动与能量", 26),
    (1, "第三章 声", 42),
    (1, "第四章 在光的世界里", 62),
    (1, "第五章 物态变化", 96),
    (1, "第六章 质量与密度", 118),
]

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
    (2, "2.3 等式与方程", 86),
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


# Independent scan: printed two-column TOC, manually transcribed before recognition.
# Existing bookmarks are generic page names and cannot serve as title labels.
ZH_INDEPENDENT = [
    (1, "第十二章 分式和分式方程", 5),
    (2, "12.1 分式", 6),
    (2, "12.2 分式的乘除", 11),
    (2, "12.3 分式的加减", 16),
    (2, "12.4 分式方程", 22),
    (2, "12.5 分式方程的应用", 26),
    (1, "第十三章 全等三角形", 35),
    (2, "13.1 命题与证明", 36),
    (2, "13.2 全等图形", 39),
    (2, "13.3 全等三角形的判定", 42),
    (2, "13.4 三角形的尺规作图", 56),
    (1, "第十四章 实数", 63),
    (2, "14.1 平方根", 64),
    (2, "14.2 立方根", 70),
    (2, "14.3 实数", 73),
    (2, "14.4 近似数", 83),
    (2, "14.5 用计算器求平方根与立方根", 86),
    (1, "第十五章 二次根式", 93),
    (2, "15.1 二次根式", 94),
    (2, "15.2 二次根式的乘除运算", 99),
    (2, "15.3 二次根式的加减运算", 102),
    (2, "15.4 二次根式的混合运算", 105),
    (1, "第十六章 轴对称和中心对称", 111),
    (2, "16.1 轴对称", 112),
    (2, "16.2 线段的垂直平分线", 116),
    (2, "16.3 角的平分线", 124),
    (2, "16.4 中心对称图形", 128),
    (2, "16.5 利用图形的平移、旋转和轴对称设计图案", 132),
    (1, "第十七章 特殊三角形", 143),
    (2, "17.1 等腰三角形", 144),
    (2, "17.2 直角三角形", 151),
    (2, "17.3 勾股定理", 154),
    (2, "17.4 直角三角形全等的判定", 163),
    (2, "17.5 反证法", 166),
]


def main():
    directory = ROOT / "validation"
    directory.mkdir(exist_ok=True)
    selected = sys.argv[1:] or list(SOURCES) + ["zh-low"]
    import pytesseract

    environment = {
        name: importlib.metadata.version(name)
        for name in ("PyMuPDF", "Pillow", "pytesseract", "packaging")
    }
    environment["tesseract"] = str(pytesseract.get_tesseract_version())
    language_list = subprocess.run(
        [app.find_tesseract(), "--list-langs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    model_directory = re.search(r'"([^"\n]+)"', language_list.splitlines()[0])
    environment["language_data_sha256"] = (
        {
            language: digest(Path(model_directory[1]) / (language + ".traineddata"))
            for language in ("eng", "chi_sim")
        }
        if model_directory
        else {}
    )
    extraction_hash = hashlib.sha256(
        (
            inspect.getsource(app.read_pages)
            + inspect.getsource(app.clean_ocr_line)
            + inspect.getsource(app.match_heading)
            + inspect.getsource(app.page_needs_ocr)
            + (ROOT / "scripts/ocr.py").read_text()
        ).encode()
    ).hexdigest()
    benchmark_hash = digest(Path(__file__))
    implementation = {
        p.name: digest(p) for p in sorted((ROOT / "scripts").glob("*.py"))
    }
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
        cache_hit = (
            cached.get("key") == key and cached.get("environment") == environment
        )
        if cache_hit:
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
                        environment=environment,
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
                source,
                app.build_tree_from_headings(headings),
                output,
                "full",
                overwrite=True,
            )
            with fitz.open(output) as doc:
                toc = doc.get_toc()
        else:
            toc = []
        automatic_seconds = time.perf_counter() - started
        reviewed_seconds = 0
        if name in {"text", "blind-java"}:
            metrics = score(reference, toc)
            if name == "text":
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
            labels = {
                "zh-exam": ZH_EXAM,
                "zh-text": ZH_TEXT,
                "zh-independent": ZH_INDEPENDENT,
                "zh-blind-physics": ZH_BLIND_PHYSICS,
            }.get(base, ZH_SCAN)
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
            if base == "zh-blind-physics":
                candidates = [row for row in toc if re.match(r"^第.*章", row[1])]
            metrics = score(labels, candidates)
            metrics["unscored_candidates"] = len(toc) - len(candidates)
            scope = "Manual chapter/numbered-section labels only, or the four question-type headers; not every visual candidate"
            if base == "zh-blind-physics":
                scope = "Six chapter titles, PDF pages and depth only; sections and visual titles are unlabelled"
            # Reviewed TOC is the documented fallback, independent of automatic recognition.
            reviewed = directory / (name + "-reviewed.pdf")
            reviewed_labels = (
                labels
                if labels[0][0] == 1
                else [(1, "2025年普通高等学校招生全国统一考试（新I卷数学）", 1)]
                + labels
            )
            reviewed_started = time.perf_counter()
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
                overwrite=True,
            )
            with fitz.open(reviewed) as doc:
                assert doc.get_toc() == [list(row) for row in reviewed_labels]
            reviewed_seconds = time.perf_counter() - reviewed_started
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
            extraction_cache_hit=cache_hit,
            evaluation_role="held_out_for_v0.3.1"
            if "blind" in name
            else "development_regression",
            save_and_verify_seconds=round(automatic_seconds, 2),
            reviewed_save_and_verify_seconds=round(reviewed_seconds, 2),
            automatic_content_preserved=bool(toc),
            reviewed_toc_verified=base.startswith("zh"),
            derived_low_quality=name == "zh-low",
            scope=scope,
            metrics=metrics,
            toc=toc,
            reference_toc=reference
            if name in {"text", "blind-java"}
            else labels
            if name.startswith("zh")
            else [],
            review_signals=dict(
                unreadable_toc_rows=sum(
                    int(line.split("\t")[1])
                    for _, text in pages
                    for line in text.splitlines()
                    if line.startswith("[TOC_REVIEW]\t")
                ),
                low_confidence_toc_rows=sum(
                    int(line.split("\t")[2])
                    for _, text in pages
                    for line in text.splitlines()
                    if line.startswith("[TOC_REVIEW]\t")
                ),
            ),
            recognition_method="printed_toc"
            if any(h.get("source") == "printed_toc" for h in headings)
            else "body_headings",
        )
        rows.append(row)
        print(
            json.dumps({k: v for k, v in row.items() if k != "toc"}, ensure_ascii=True),
            flush=True,
        )
    assert implementation == {
        p.name: digest(p) for p in sorted((ROOT / "scripts").glob("*.py"))
    }, "Implementation changed during benchmark; rerun without editing sources"
    results = dict(
        version=app.VERSION,
        environment=environment,
        timing_note="Recognition time measures the original extraction; cached reruns do not remeasure it. Save/verify is measured on each run.",
        python=sys.version,
        pymupdf=fitz.VersionBind,
        tesseract=str(__import__("pytesseract").get_tesseract_version()),
        implementation_sha256=implementation,
        benchmark_sha256=benchmark_hash,
        annotation_notes=[
            "Beijing section 2.3 corrected to 等式与方程 after checking printed TOC and body page 86; prior label 算式与等式 was incorrect.",
            "Independent Jijiao scan has generic page bookmarks; labels are manually transcribed, not extracted from those bookmarks.",
            "Think Java and Jiaoke physics were first evaluated after freezing v0.3.1 recognition. No recognition changes were made after seeing their results. Physics is a mixed PDF, not an image-only scan; six chapters only are labelled. These samples become regression data for later releases.",
        ],
        results=rows,
    )
    (directory / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
