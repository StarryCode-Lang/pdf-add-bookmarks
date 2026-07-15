#!/usr/bin/env python3
"""
Generate test PDF fixtures for the pdf-add-bookmarks test suite.
Uses reportlab to create text-based PDFs with controlled heading structures.
"""
import os, sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# Register Chinese font
def _register_chinese_font():
    candidates = [
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", path))
                return "ChineseFont"
            except Exception:
                continue
    return "Helvetica"

CHINESE_FONT = _register_chinese_font()
CHINESE_FONT_AVAILABLE = CHINESE_FONT != "Helvetica"

def build_pdf(filename, pages_data, font_name="Helvetica", font_size=12):
    """Build a PDF with given pages. Each page is (heading, body_text)."""
    path = FIXTURES_DIR / filename
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)

    heading_style = ParagraphStyle(
        "Heading1", fontName=font_name, fontSize=18,
        spaceAfter=12, spaceBefore=6, leading=22
    )
    body_style = ParagraphStyle(
        "Body", fontName=font_name, fontSize=font_size,
        spaceAfter=6, leading=font_size * 1.5
    )

    story = []
    for i, (heading, body) in enumerate(pages_data):
        if i > 0:
            story.append(PageBreak())
        if heading:
            story.append(Paragraph(heading, heading_style))
            story.append(Spacer(1, 12))
        if body:
            story.append(Paragraph(body, body_style))

    doc.build(story)
    print(f"  Created: {path} ({len(pages_data)} pages)")
    return path


def main():
    print("Generating test PDF fixtures...\n")

    # TC01: Chinese text-based PDF with full heading hierarchy
    chinese_font = CHINESE_FONT if CHINESE_FONT_AVAILABLE else "Helvetica"
    chinese_lorem = (
        "本研究旨在探讨现代机器学习方法在工业故障诊断中的应用。"
        "随着工业4.0的推进，设备状态监测和故障预测变得越来越重要。"
        "传统的故障诊断方法依赖于专家经验和规则系统，难以应对复杂多变的工业环境。"
    )
    build_pdf("chinese_text.pdf", [
        ("第1章 概述", chinese_lorem * 2),
        ("1.1 研究背景", chinese_lorem),
        ("1.1.1 历史回顾", chinese_lorem),
        ("1.2 研究目标", chinese_lorem),
        ("第2章 方法", chinese_lorem * 2),
        ("2.1 实验设计", chinese_lorem),
        ("2.1.1 数据采集", chinese_lorem),
    ], font_name=chinese_font, font_size=12)

    # TC02: English text-based PDF with numbered headings
    english_lorem = (
        "This research investigates the application of modern machine learning "
        "techniques in industrial fault diagnosis. With the advancement of Industry 4.0, "
        "equipment condition monitoring and fault prediction have become increasingly critical."
    )
    build_pdf("english_text.pdf", [
        ("1. Introduction", english_lorem * 3),
        ("1.1 Background", english_lorem),
        ("1.1.1 Historical Context", english_lorem),
        ("Chapter 2 Methods", english_lorem * 3),
        ("2.1 Experimental Design", english_lorem),
        ("2.1.1 Data Collection", english_lorem),
    ])

    # TC05: Single-page PDF
    build_pdf("single_page.pdf", [
        ("第1章 引言", chinese_lorem),
    ], font_name=chinese_font, font_size=12)

    # TC06: PDF with no headings
    build_pdf("no_headings.pdf", [
        (None, "This is a plain paragraph with no heading patterns at all. " * 5),
        (None, "Another page of plain text that contains no recognizable headings. " * 5),
        (None, "The third page also has no headings, just normal prose content. " * 5),
    ])

    # TC07: Image-only PDF (colored rectangles, no text)
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Image
    from reportlab.graphics.shapes import Drawing, Rect
    img_path = build_pdf("images_only.pdf", [
        (None, None), (None, None), (None, None),
    ])
    # Overwrite with actual image-only content
    from reportlab.platypus import Flowable
    class ColorRect(Flowable):
        def __init__(self, w, h, color):
            Flowable.__init__(self)
            self._w = w
            self._h = h
            self._color = color
        def draw(self):
            self.canv.setFillColor(self._color)
            self.canv.rect(0, 0, self._w, self._h, fill=1, stroke=0)
        def wrap(self, availWidth, availHeight):
            return (self._w, self._h)
    doc = SimpleDocTemplate(str(img_path), pagesize=A4)
    story = []
    colors = [HexColor("#FF6B6B"), HexColor("#4ECDC4"), HexColor("#45B7D1")]
    for i in range(3):
        if i > 0:
            story.append(PageBreak())
        story.append(Spacer(1, 3*cm))
        story.append(ColorRect(400, 300, colors[i]))
    doc.build(story)
    print(f"  Overwritten: {img_path} (3 pages, images only)")

    # TC08: Large PDF (100 pages)
    large_pages = []
    for i in range(100):
        section = i // 10
        heading = f"第{section+1}章 测试章节" if chinese_font == "Helvetica" else f"Chapter {section+1} Test"
        body = f"Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt. " * 4
        if i % 10 == 0:
            large_pages.append((heading, body))
        else:
            large_pages.append((None, body))
    build_pdf("large.pdf", large_pages, font_name=chinese_font, font_size=10)

    # TOC files
    toc_content = "\n".join([
        "第1章 概述 1",
        "  1.1 研究背景 2",
        "    1.1.1 历史回顾 3",
        "  1.2 研究目标 4",
        "第2章 方法 5",
        "  2.1 实验设计 6",
        "    2.1.1 数据采集 7",
    ])
    (FIXTURES_DIR / "toc.txt").write_text(toc_content, encoding="utf-8")
    print(f"  Created: {FIXTURES_DIR / 'toc.txt'}")

    toc_offset = "\n".join([
        "第1章 概述 3",
        "  1.1 研究背景 4",
        "第2章 方法 7",
    ])
    (FIXTURES_DIR / "toc_offset.txt").write_text(toc_offset, encoding="utf-8")
    print(f"  Created: {FIXTURES_DIR / 'toc_offset.txt'}")

    # English TOC
    toc_en = "\n".join([
        "1. Introduction 1",
        "  1.1 Background 2",
        "    1.1.1 Historical Context 3",
        "Chapter 2 Methods 4",
        "  2.1 Experimental Design 5",
        "    2.1.1 Data Collection 6",
    ])
    (FIXTURES_DIR / "toc_en.txt").write_text(toc_en, encoding="utf-8")
    print(f"  Created: {FIXTURES_DIR / 'toc_en.txt'}")

    print("\nAll fixtures generated.")


if __name__ == "__main__":
    main()