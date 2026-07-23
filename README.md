# PDF Add Bookmarks

Add hierarchical bookmarks/outline (章→节→小节) to PDF files. Supports **textbooks**, **exam papers**, **slides**, and **articles** with type-specific heading detection. Auto-detects text-based vs scanned PDFs, uses OCR for scanned ones.

## Features

- **PDF Type Detection** — Auto-detects textbook/exam/slides/article
- **Type-Specific Patterns** — Each PDF type uses appropriate heading patterns
- **OCR Support** — Automatically detects and OCRs scanned/image-based PDFs
- **Multiprocessing OCR** — Parallel processing across CPU cores for fast OCR
- **Smart Fallback** — When no headings found, generates candidate TOC via full page analysis
- **Analyze Mode** — OCR all pages, show content summary, generate suggested TOC
- **TOC File Mode** — Import bookmarks from a text table of contents
- **Content Integrity** — Verifies original content is preserved
- **Cross-Platform** — Windows, macOS, Linux
- **Multi-Agent Support** — Install as plugin/skill for Claude Code, OpenCode, Hermes, OpenClaw, Kimi Code

## PDF Type Detection

| Type | Detection Heuristics | Example Headings |
|------|---------------------|-----------------|
| **textbook** | 第X章, Chapter, numbered sections | 第3章 顺序表, 2.1 栈 |
| **exam** | 20XX年真题, 统考, 试题 | 2024年真题, 2025统考 |
| **slides** | Bullets, short titles, outline markers | 一、概述, 1. 背景 |
| **article** | Abstract, Introduction, References | 1. Introduction |
| **auto** | Combined scoring (default) | — |

## Quick Start

```bash
pip install pymupdf pytesseract pillow
python scripts/add_bookmarks.py "input.pdf"
```

Output: `input_with_bookmarks.pdf`

## Usage

### Auto-detect (default)

Detects PDF type and uses appropriate heading patterns:
```bash
python scripts/add_bookmarks.py "input.pdf"
```

### Analyze (preview before bookmarking)

OCR all pages, show a content summary, and generate a suggested TOC file:
```bash
python scripts/add_bookmarks.py "input.pdf" --analyze
```
Output: `input_suggested_toc.txt` (review, edit, then re-run with `--toc`)

### Auto-generate TOC

OCR all pages, analyze content structure, and auto-generate bookmarks:
```bash
python scripts/add_bookmarks.py "input.pdf" --generate-toc
```

### TOC File Mode

```bash
python scripts/add_bookmarks.py "input.pdf" --toc toc.txt [--offset N]
```

TOC format (indentation-based hierarchy):
```
第1章 概述 1
  1.1 背景 2
    1.1.1 研究现状 3
  1.2 目标 10
第2章 方法 15
```

### Force OCR

```bash
python scripts/add_bookmarks.py "scanned.pdf" --force-ocr
```

### Specify PDF Type

```bash
python scripts/add_bookmarks.py "exam.pdf" --type exam
python scripts/add_bookmarks.py "slides.pdf" --type slides
```

## Supported Heading Formats

| Language | Pattern | Example |
|----------|---------|---------|
| Chinese | `第X章 标题` | 第1章 概述 |
| Chinese | `X 标题` | 2 顺序表 |
| Chinese | `X.X 标题` | 2.1 背景 |
| Chinese | `X.X.X 标题` | 2.1.1 研究现状 |
| Chinese | `20XX年 真题/应用题` | 2024年真题应用题 |
| Chinese | `第X讲 标题` | 第5讲 直播课 |
| Chinese | `一、标题 / （一）标题` | 一、备考策略 |
| English | `X. Title` | 1. Introduction |
| English | `Chapter X` | Chapter 2 |
| English | `A.1. Title` | A.1. Classification |

## All Options

```
usage: add_bookmarks.py [-h] [-o OUTPUT] [--lang LANG] [--force-ocr]
                        [--toc TOC] [--offset OFFSET] [--workers WORKERS]
                        [--analyze] [--generate-toc]
                        [--type {auto,textbook,exam,slides,article}]
                        input
```

## Multi-Agent Installation

See [install/INDEX.md](install/INDEX.md) for installation guides on:

| Agent | Type | Quick Install |
|-------|------|--------------|
| **Claude Code** | Plugin | `install/claude-code/README.md` |
| **OpenCode** | Skill | `install/opencode/README.md` |
| **Hermes** | Skill | `install/hermes/README.md` |
| **OpenClaw** | Skill | `install/openclaw/README.md` |
| **Kimi Code** | Plugin | `install/kimi-code/README.md` |
| **Other** | Manual | `install/manual/README.md` |

### Auto-install (Windows PowerShell)
```powershell
.\install\install.ps1
```

### Auto-install (macOS/Linux)
```bash
chmod +x install/install.sh && ./install/install.sh
```

## Direct Dependency Setup

```bash
pip install pymupdf pytesseract pillow
```

For scanned PDFs, also install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) with Chinese language data (see `references/dependencies.md`).

## Project Structure

```
pdf-add-bookmarks/
├── SKILL.md                    # Agent skill definition (v2)
├── _meta.json                  # Marketplace metadata
├── README.md                   # This file
├── .gitignore
├── scripts/
│   └── add_bookmarks.py        # Main script (v2.0)
├── references/
│   └── dependencies.md         # Cross-platform dependency setup
├── install/                    # Multi-agent installation
│   ├── INDEX.md
│   ├── install.ps1             # Windows auto-installer
│   ├── install.sh              # macOS/Linux auto-installer
│   ├── claude-code/            # Claude Code plugin
│   ├── opencode/               # OpenCode skill
│   ├── hermes/                 # Hermes skill
│   ├── openclaw/               # OpenClaw skill
│   ├── kimi-code/              # Kimi Code plugin
│   └── manual/                 # Generic/other agents
└── tests/
    └── test_add_bookmarks.py   # Pytest suite
```

## License

MIT
