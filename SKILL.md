---
name: pdf-add-bookmarks
description: Add hierarchical bookmarks/outline (章→节→小节) to PDF files. Auto-detects text-based vs scanned PDFs, uses OCR for scanned ones. Supports multiple PDF types (textbook/exam/slides/article) with type-specific heading detection. Smart fallback generates candidate TOC when no headings found. Use when user asks to add bookmarks, outline, table of contents, or navigation structure to a PDF. Triggers on: "add bookmarks", "add outline", "为PDF添加书签", "PDF大纲", "PDF目录", "PDF navigation", or providing a PDF path and asking for bookmarks.
metadata:
  short-description: Add hierarchical bookmarks to PDF files with OCR, PDF type detection, and smart fallback
  category: productivity
  tags: [pdf, bookmark, outline, ocr, chinese, exam, slides]
  author: StarryCode-Lang
  version: 2.0.0
  repository: https://github.com/StarryCode-Lang/pdf-add-bookmarks.git
---

# PDF Add Bookmarks

Add hierarchical bookmarks (章→节→小节) to PDF files. Supports **textbooks**, **exam papers**, **slides**, and **articles** with type-specific heading detection. Auto-detects text-based vs scanned PDFs, uses OCR (multiprocessing) for scanned ones.

## Quick Start

```bash
pip install pymupdf pytesseract pillow
python scripts/add_bookmarks.py "file.pdf"
```

Output: `file_with_bookmarks.pdf`

## PDF Type Support

| Type | Detection | Example Headings |
|------|-----------|-----------------|
| Textbook | 第X章, X.X, Chapter X | 第3章 顺序表, 2.1 栈 |
| Exam | 20XX年真题, 统考, 试题 | 2024年真题应用题 |
| Slides | 一、, bullet points, short titles | 一、备考策略 |
| Article | Abstract, Introduction, References | 1. Introduction |
| Auto | All patterns combined | — |

## Usage Modes

### Auto-detect (default)
Script detects PDF type and uses appropriate heading patterns:
```bash
python scripts/add_bookmarks.py "file.pdf"
```

### Analyze Mode
OCR all pages, show content summary, generate a suggested TOC file for review:
```bash
python scripts/add_bookmarks.py "file.pdf" --analyze
```
Output: `file_suggested_toc.txt` (review/edit then use with `--toc`)

### Auto-generate TOC
OCR all pages, analyze content, generate bookmarks automatically:
```bash
python scripts/add_bookmarks.py "file.pdf" --generate-toc
```

### TOC File Mode
Import bookmarks from a text file:
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

### Force OCR
```bash
python scripts/add_bookmarks.py "file.pdf" --force-ocr
```

## All Options

```
usage: add_bookmarks.py [-h] [-o OUTPUT] [--lang LANG] [--force-ocr]
                        [--toc TOC] [--offset OFFSET] [--workers WORKERS]
                        [--analyze] [--generate-toc]
                        [--type {auto,textbook,exam,slides,article}]
                        input

positional arguments:
  input                 Input PDF file path

options:
  -o, --output          Output PDF path (default: *_with_bookmarks.pdf)
  --lang LANG           Tesseract OCR language (default: chi_sim+eng)
  --force-ocr           Force OCR mode
  --toc TOC             TOC text file path (title+page per line)
  --offset OFFSET       Page offset for TOC mode
  --workers WORKERS     Number of OCR worker processes
  --analyze             Analyze PDF: OCR all pages, show content summary,
                        generate suggested TOC file
  --generate-toc        Auto-generate TOC by OCR+analyzing all pages,
                        then add bookmarks
  --type                PDF type hint (auto/textbook/exam/slides/article)
```

## Dependencies

See `references/dependencies.md` for cross-platform tesseract + Chinese language data setup.

Required: `pymupdf` `pytesseract` `pillow` + `tesseract-ocr` system tool.

## Multi-Agent Installation

See `install/INDEX.md` for installation guides for:
- **Claude Code** — Plugin with `/pdf-add-bookmarks` command
- **OpenCode** — Agent/skill definition
- **Hermes** — Skill with SKILL.md
- **OpenClaw** — Skill config
- **Kimi Code** — Plugin config
- **Other agents** — Manual script usage
