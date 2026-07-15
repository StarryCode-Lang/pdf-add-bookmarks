---
name: pdf-add-bookmarks
description: Add hierarchical bookmarks/outline (章→节→小节) to PDF files. Auto-detects text-based vs scanned PDFs, uses OCR for scanned ones. Supports both Chinese and English heading patterns. Use when user asks to add bookmarks, outline, table of contents, or navigation structure to a PDF. Triggers on: "add bookmarks", "add outline", "为PDF添加书签", "PDF大纲", "PDF目录", "PDF navigation", or providing a PDF path and asking for bookmarks.
metadata:
  short-description: Add hierarchical bookmarks to PDF files with OCR support for scanned documents
  category: productivity
  tags: [pdf, bookmark, outline, ocr]
---

# PDF Add Bookmarks

Run the script on the user's PDF. It auto-detects everything and outputs a new file with bookmarks.

## Quick Start

```bash
pip install pymupdf pytesseract pillow
python scripts/add_bookmarks.py "file.pdf"
```

Output: `file_with_bookmarks.pdf`

## Modes

**Auto-detect (default):** Script detects if PDF is text-based or scanned. Supports heading patterns:
- `第X章` / `X 标题` / `X.X 标题` / `X.X.X 标题` (Chinese)
- `X. Title` / `Chapter X` / `Part X` (English)
- `A.1. Subsection` (Appendix)

**TOC file mode:** Import bookmarks from a text table of contents:

```bash
python scripts/add_bookmarks.py "file.pdf" --toc toc.txt [--offset N]
```

TOC format — one entry per line, indentation for hierarchy:
```
第1章 概述 1
  1.1 背景 2
    1.1.1 研究现状 3
  1.2 目标 10
第2章 方法 15
```

**Force OCR:** `--force-ocr` flag for PDFs with watermarks confusing text detection.

## Dependencies

See `references/dependencies.md` for cross-platform tesseract + Chinese language data setup.

Required: `pymupdf` `pytesseract` `pillow` + `tesseract-ocr` system tool.