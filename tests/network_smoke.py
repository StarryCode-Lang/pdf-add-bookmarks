"""Optional real-document benchmark: pinned sources, independent labels, local evidence."""

import base64
import hashlib
import importlib.metadata
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
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
# Originally held out at v0.3.1; these cases are now development regressions.
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

SOURCES["zh-heldout-suke"] = (
    TEXTBOOK
    + urllib.parse.quote(
        "初中/物理/苏科版-江苏凤凰科学技术出版社/八年级/义务教育教科书·物理八年级上册.pdf"
    ),
    "020e05765e8373111f5e71604d56f02bdeafa14ab9913344253f92f89d0ace98",
    "chi_sim+eng",
    "textbook",
)
ZH_HELDOUT_SUKE = [
    (1, "第一章 声现象", 14),
    (1, "第二章 物态变化", 34),
    (1, "第三章 光现象", 60),
    (1, "第四章 光的折射 透镜", 86),
    (1, "第五章 物体的运动", 108),
]
# Complete printed contents; used to develop v0.4.0, no longer held out.
SOURCES["zh-blind-geography"] = (
    TEXTBOOK
    + urllib.parse.quote(
        "初中/地理/湘教版-湖南教育出版社/七年级/义务教育教科书·地理七年级上册.pdf"
    ),
    "36f9579d703ab2f3ade102402f77eddd7e04630fa151738ddf588c74f0a57064",
    "chi_sim+eng",
    "textbook",
)
ZH_BLIND_GEOGRAPHY = [
    (1, "第一章 让我们走进地理", 8),
    (2, "第一节 我们身边的地理", 9),
    (2, "第二节 我们怎样学地理", 14),
    (1, "第二章 地球的面貌", 22),
    (2, "第一节 认识地球", 23),
    (2, "第二节 世界的海陆分布", 35),
    (2, "第三节 世界的地形", 40),
    (2, "第四节 海陆变迁", 47),
    (1, "第三章 世界的居民", 54),
    (2, "第一节 世界的人口", 55),
    (2, "第二节 世界的人种", 61),
    (2, "第三节 世界的语言与宗教", 63),
    (2, "第四节 世界的聚落", 67),
    (1, "第四章 世界的气候", 73),
    (2, "第一节 天气和气候", 74),
    (2, "第二节 气温和降水", 78),
    (2, "第三节 影响气候的主要因素", 85),
    (2, "第四节 世界主要气候类型", 94),
    (1, "第五章 世界的发展差异", 106),
    (2, "第一节 发展中国家与发达国家", 107),
    (2, "第二节 国际经济合作", 113),
    (1, "附录一 英汉地理词汇", 117),
    (1, "附录二 常用地图图例", 119),
    (1, "后记", 120),
]

# Complete biology contents; used to develop v0.4.0, no longer held out.
SOURCES["zh-blind-biology"] = (
    TEXTBOOK
    + urllib.parse.quote(
        "初中/生物学/济南版-济南出版社/七年级/义务教育教科书·生物学七年级上册.pdf"
    ),
    "87750a8ef0b557d736542fbaf4b7f2fca0dcf9372ba139c511249420b6bd00ce",
    "chi_sim+eng",
    "textbook",
)
ZH_BLIND_BIOLOGY = [
    (1, "第一单元 奇妙的生命现象", 7),
    (2, "第一章 认识生命现象", 8),
    (3, "第一节 生物的基本特征", 9),
    (3, "第二节 生物的生活环境", 12),
    (3, "第三节 生物学的探究方法", 16),
    (3, "第四节 生物学的研究工具", 20),
    (2, "第二章 观察生物结构", 28),
    (3, "第一节 细胞的结构和功能", 29),
    (3, "第二节 细胞的分裂与分化", 37),
    (3, "第三节 多细胞生物体的结构层次", 41),
    (1, "第二单元 多彩的生物世界", 45),
    (2, "第一章 生物圈中的绿色植物", 46),
    (3, "第一节 绿色植物的主要类群", 47),
    (3, "第二节 绿色植物的蒸腾作用", 54),
    (3, "第三节 绿色植物的光合作用", 60),
    (3, "第四节 绿色植物的呼吸作用", 66),
    (3, "第五节 绿色植物在生物圈中的作用", 70),
    (2, "第二章 生物圈中的动物", 77),
    (3, "第一节 无脊椎动物的主要类群", 78),
    (3, "第二节 脊椎动物的主要类群", 86),
    (3, "第三节 动物的运动", 96),
    (3, "第四节 动物的行为", 100),
    (3, "第五节 动物在生物圈中的作用", 106),
    (2, "第三章 生物圈中的微生物", 111),
    (3, "第一节 病毒", 112),
    (3, "第二节 细菌", 116),
    (3, "第三节 真菌", 121),
    (3, "第四节 微生物在生物圈中的作用", 125),
    (2, "第四章 生物的分类", 129),
    (3, "第一节 生物的分类方法", 130),
    (3, "第二节 生物的分类单位", 133),
    (1, "附录", 138),
]
COMPLETE_CONTENT_LABELS = {
    "zh-blind-geography": ZH_BLIND_GEOGRAPHY,
    "zh-blind-biology": ZH_BLIND_BIOLOGY,
}

# New books selected after freezing v0.4.0 recognition, labelled before first run.
SOURCES["zh-heldout-chemistry"] = (
    TEXTBOOK
    + urllib.parse.quote(
        "初中/化学/沪教版-上海教育出版社/九年级/义务教育教科书·化学九年级上册.pdf"
    ),
    "b509a71fb2f35871d4cfa772a4df7f53d84e962d75e0dfc2957c0505aef40bd6",
    "chi_sim+eng",
    "textbook",
)
SOURCES["zh-heldout-guangdong"] = (
    TEXTBOOK
    + urllib.parse.quote(
        "初中/地理/粤教粤人版-广东教育出版社、广东人民出版社/七年级/义务教育教科书·地理七年级上册.pdf"
    ),
    "c5d622634527cf67f0370b2e6419e1c66aa9a62f0fd8df036aa813196f62547e",
    "chi_sim+eng",
    "textbook",
)
ZH_HELDOUT_CHEMISTRY = [
    (1, "第1章 开启化学之门", 6),
    (2, "第1节 化学给我们带来什么", 7),
    (2, "第2节 化学研究些什么", 14),
    (2, "第3节 怎样学习和研究化学", 25),
    (2, "整理与归纳", 31),
    (2, "本章作业", 32),
    (1, "第2章 身边的化学物质", 34),
    (2, "第1节 性质活泼的氧气", 35),
    (2, "第2节 奇妙的二氧化碳", 44),
    (2, "第3节 自然界中的水", 52),
    (2, "基础实验1 氧气的制取与性质", 60),
    (2, "基础实验2 二氧化碳的制取与性质", 62),
    (2, "整理与归纳", 63),
    (2, "本章作业", 64),
    (1, "第3章 物质构成的奥秘", 66),
    (2, "第1节 构成物质的基本微粒", 67),
    (2, "第2节 组成物质的化学元素", 79),
    (2, "第3节 物质的组成", 86),
    (2, "整理与归纳", 93),
    (2, "本章作业", 94),
    (1, "第4章 认识化学变化", 96),
    (2, "第1节 常见的化学反应——燃烧", 97),
    (2, "第2节 化学反应中的质量关系", 105),
    (2, "第3节 化学方程式的书写与应用", 109),
    (2, "基础实验3 物质燃烧的条件", 114),
    (2, "整理与归纳", 115),
    (2, "本章作业", 116),
    (1, "第5章 金属的冶炼与利用", 118),
    (2, "第1节 金属的性质和利用", 119),
    (2, "第2节 金属矿物 铁的冶炼", 128),
    (2, "第3节 金属防护和废金属回收", 132),
    (2, "基础实验4 常见金属的性质", 137),
    (2, "整理与归纳", 140),
    (2, "本章作业", 141),
    (1, "附录", 142),
]
ZH_HELDOUT_GUANGDONG = [
    (1, "让地理走进生活", 8),
    (1, "第一章 认识地球", 14),
    (2, "第一节 地球的形状与大小", 15),
    (2, "第二节 地球仪", 18),
    (2, "第三节 地球的运动", 24),
    (1, "第二章 学用地图", 30),
    (2, "第一节 地图的发展", 31),
    (2, "第二节 地图的运用", 34),
    (2, "第三节 等高线与地形图的判读", 40),
    (1, "第三章 陆地与海洋", 45),
    (2, "第一节 陆地与海洋的分布", 46),
    (2, "第二节 海洋与陆地的变迁", 51),
    (2, "第三节 人类与海洋", 56),
    (1, "第四章 天气与气候", 59),
    (2, "第一节 天气和天气预报", 60),
    (2, "第二节 气温和降水", 67),
    (2, "第三节 世界的主要气候类型", 75),
    (1, "第五章 居民与聚落", 82),
    (2, "第一节 世界的人口", 83),
    (2, "第二节 世界的人种、语言和宗教", 89),
    (2, "第三节 聚落的发展变化", 94),
    (1, "第六章 发展差异与国际合作", 100),
]
COMPLETE_CONTENT_LABELS.update(
    {
        "zh-heldout-chemistry": ZH_HELDOUT_CHEMISTRY,
        "zh-heldout-guangdong": ZH_HELDOUT_GUANGDONG,
    }
)
INDEPENDENT_SAMPLES = {"zh-heldout-chemistry", "zh-heldout-guangdong"}

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
    title = re.sub(r"^第[一二三四五六七八九十百\d]+[章节]\s*", "", title)
    title = re.sub(
        r"^(Chapter|Part|Appendix)\s+(\d+|[A-Z]+)\.?\s+|^\d+(?:\.\d+)*\.?\s+|^[A-Z]\.(?:\d+\.)*\d*\.?\s+",
        "",
        title,
        flags=re.I,
    )
    return re.sub(r"\W", "", title).lower()


def score(reference, candidates):
    expected = {(level, normalize(title), page) for level, title, page in reference}
    counts = Counter(
        (level, normalize(title), page) for level, title, page in candidates
    )
    actual = set(counts)
    matched = len(expected & actual)
    return dict(
        reference_entries=len(expected),
        scored_candidates=len(candidates),
        duplicate_candidates=sum(count - 1 for count in counts.values()),
        exact_matches=matched,
        precision=matched / len(candidates) if candidates else 0,
        recall=matched / len(expected),
        missing=sorted(expected - actual),
        unexpected=sorted(actual - expected),
    )


def review_complete_contents(reference, candidates):
    """Classify every candidate against the predefined, complete printed outline."""
    expected = {(level, normalize(title), page) for level, title, page in reference}
    seen = set()
    reviewed = []
    for level, title, page in candidates:
        key = (level, normalize(title), page)
        if key in expected:
            status = "duplicate" if key in seen else "exact_match"
        elif any(normalize(t) == key[1] and p == page for _, t, p in reference):
            status = "wrong_depth"
        elif any(normalize(t) == key[1] for _, t, _ in reference):
            status = "wrong_destination"
        else:
            status = "outside_printed_contents_or_ocr_error"
        seen.add(key)
        reviewed.append(dict(bookmark=[level, title, page], assessment=status))
    return reviewed


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


def verify_signed_fixture():
    """Verify the real CMS signature without treating its test certificate as a public CA."""
    data = base64.decodebytes((ROOT / "tests/fixtures/signed_pdf.b64").read_bytes())
    ranges = [int(v) for v in re.search(rb"/ByteRange\s*\[([^]]+)\]", data)[1].split()]
    assert len(ranges) == 4 and ranges[0] == 0 and ranges[2] + ranges[3] == len(data)
    content = data[: ranges[1]] + data[ranges[2] :]
    cms = bytes.fromhex(
        re.search(rb"/Contents\s*<([0-9a-f]+)>", data, re.I)[1].decode()
    )
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        (folder / "content").write_bytes(content)
        (folder / "signature.der").write_bytes(cms)
        subprocess.run(
            [
                "openssl",
                "cms",
                "-verify",
                "-binary",
                "-noverify",
                "-inform",
                "DER",
                "-in",
                str(folder / "signature.der"),
                "-content",
                str(folder / "content"),
            ],
            capture_output=True,
            check=True,
        )
    return dict(
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
        cryptographic_integrity_verified=True,
        certificate_trust="Self-signed test certificate; public CA trust is not asserted",
        validator="OpenSSL CMS verify",
    )


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
                "zh-heldout-suke": ZH_HELDOUT_SUKE,
                **COMPLETE_CONTENT_LABELS,
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
            if base in {"zh-blind-physics", "zh-heldout-suke"}:
                candidates = [
                    row
                    for row in toc
                    if re.match(r"^第.*章", row[1])
                    or (
                        row[0] == 1
                        and normalize(row[1]) in {normalize(t) for _, t, _ in labels}
                    )
                ]
            if base in COMPLETE_CONTENT_LABELS:
                candidates = toc
            metrics = score(labels, candidates)
            metrics["unscored_candidates"] = len(toc) - len(candidates)
            scope = "Manual chapter/numbered-section labels only, or the four question-type headers; not every visual candidate"
            if base in {"zh-blind-physics", "zh-heldout-suke"}:
                scope = "Chapter titles, PDF pages and depth only; sections and visual titles are unlabelled"
            if base in COMPLETE_CONTENT_LABELS:
                scope = "Complete printed contents including units and appendices; every generated bookmark is scored, including duplicates and extra titles. Extra body headings are not necessarily invalid navigation, but are outside this predefined contents policy."
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
            evaluation_role="independent_held_out"
            if base in INDEPENDENT_SAMPLES
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
        if base in COMPLETE_CONTENT_LABELS:
            row["candidate_review"] = review_complete_contents(labels, toc)
            row["reference_evidence"] = (
                "Printed contents visually transcribed before recognition, with PDF-page offset checked on body unit/chapter/section starts; not inferred from generated bookmarks."
            )
            row["assessment_counts"] = dict(
                Counter(item["assessment"] for item in row["candidate_review"])
            )
            row["title_and_page_matches_ignoring_depth"] = len(
                {(normalize(t), p) for _, t, p in labels}
                & {(normalize(t), p) for _, t, p in toc}
            )
        from headings import diagnose_outline

        row["diagnostics"] = diagnose_outline(headings, pages)
        rows.append(row)
        print(
            json.dumps({k: v for k, v in row.items() if k != "toc"}, ensure_ascii=True),
            flush=True,
        )
    assert implementation == {
        p.name: digest(p) for p in sorted((ROOT / "scripts").glob("*.py"))
    }, "Implementation changed during benchmark; rerun without editing sources"
    prior = json.loads((ROOT / "tests/benchmark_results.json").read_text())
    first_pass = prior.get("independent_first_pass", {})
    if not first_pass and (directory / "blind-first-pass.json").exists():
        first_pass = json.loads((directory / "blind-first-pass.json").read_text())
    results = dict(
        independent_first_pass=first_pass,
        prior_independent_evaluations=prior.get("prior_independent_evaluations", {}),
        version=app.VERSION,
        signed_fixture=verify_signed_fixture(),
        environment=environment,
        timing_note="Recognition time measures the original extraction; cached reruns do not remeasure it. Save/verify is measured on each run.",
        python=sys.version,
        pymupdf=fitz.VersionBind,
        tesseract=str(__import__("pytesseract").get_tesseract_version()),
        implementation_sha256=implementation,
        benchmark_sha256=benchmark_hash,
        annotation_notes=[
            "Geography and biology from v0.3.3 are now development regressions. Their initial failures and source implementation hashes are preserved under prior_independent_evaluations; only the two new v0.4.0 sources are held out.",
            "New chemistry labels include every printed contents entry: chapters, sections, repeated summaries/homework and laboratory activities; new Guangdong geography labels include the introductory entry and all chapters/sections. All generated candidates are scored.",
            "Beijing section 2.3 corrected to 等式与方程 after checking printed TOC and body page 86; prior label 算式与等式 was incorrect.",
            "Independent Jijiao scan has generic page bookmarks; labels are manually transcribed, not extracted from those bookmarks.",
            "Think Java and Jiaoke physics are now development regression data. Appendix numbering normalization was corrected in v0.3.2; earlier 205/230 was not 25 missing destinations. Jiaoke physics labels cover six chapters only.",
            "Suke physics first-pass held-out test failed (0/5); its original result and implementation hashes are preserved under independent_first_pass. Vertical-column and side-margin fixes followed, so current Suke results are development regression, not a new blind test.",
        ],
        results=rows,
    )
    (directory / os.environ.get("BENCHMARK_REPORT", "results.json")).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
