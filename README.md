# PDF Add Bookmarks

Add hierarchical bookmarks/outline (章→节→小节) to PDF files. Supports both text-based and scanned (image-based) PDFs. For scanned PDFs, uses OCR to detect heading structure.

## Installation

### Install Dependencies

```bash
pip install pypdf pymupdf pytesseract pillow
```

For scanned PDFs, also install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) with Chinese language data (see `references/dependencies.md`).

### Agent Integration

#### Claude Code

Clone or copy this repository into your Claude Code skills directory:

```bash
# Option A: Clone directly
git clone https://github.com/YOUR_USER/pdf-add-bookmarks.git \
  ~/.claude/skills/pdf-add-bookmarks

# Option B: Symlink (recommended for development)
ln -s /path/to/pdf-add-bookmarks ~/.claude/skills/pdf-add-bookmarks
```

Then use in Claude Code:
```
/pdf-add-bookmarks "document.pdf"
```

#### Codex (OpenAI)

Clone or copy into Codex skills directory:

```bash
cp -r pdf-add-bookmarks ~/.codex/skills/pdf-add-bookmarks
```

Then use in Codex:
```
Use the pdf-add-bookmarks skill to add bookmarks to document.pdf
```

#### QoderWork CN

Import the `.skill` package file from the repository's releases, or copy the skill directory to:

```
%APPDATA%\QoderWork CN\Cache\skills\packages\pdf-add-bookmarks\
```

#### Direct Use (Any Agent)

Just run the script directly:

```bash
python scripts/add_bookmarks.py "document.pdf"
```

## Usage

### Quick Start

```bash
python scripts/add_bookmarks.py "input.pdf"
```

Output: `input_with_bookmarks.pdf`

### Features

- **Auto-detect** — Text-based or scanned PDF, Chinese or English headings
- **OCR support** — Automatically detects and OCRs scanned/image-based PDFs
- **Cross-platform** — Windows, macOS, Linux
- **TOC file mode** — Import bookmarks from a text table of contents
- **Content integrity** — Verifies original content is preserved

### Supported Heading Formats

| Language | Pattern | Example |
|----------|---------|---------|
| Chinese | `第X章 标题` | 第1章 概述 |
| Chinese | `X 标题` | 2 顺序表 |
| Chinese | `X.X 标题` | 2.1 背景 |
| Chinese | `X.X.X 标题` | 2.1.1 研究现状 |
| English | `X. Title` | 1. Introduction |
| English | `Chapter X` | Chapter 2 |
| English | `A.1. Title` | A.1. Classification |

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

### Force OCR Mode

```bash
python scripts/add_bookmarks.py "scanned.pdf" --force-ocr
```

### All Options

```
usage: add_bookmarks.py [-h] [-o OUTPUT] [--lang LANG] [--force-ocr] [--toc TOC] [--offset OFFSET] input

positional arguments:
  input                 Input PDF file path

options:
  -o, --output          Output PDF path (default: *_with_bookmarks.pdf)
  --lang LANG           Tesseract OCR language (default: chi_sim+eng)
  --force-ocr           Force OCR mode
  --toc TOC             TOC text file path (title+page per line)
  --offset OFFSET       Page offset for TOC mode (default: 0)
```

## Project Structure

```
pdf-add-bookmarks/
├── SKILL.md                 # Agent skill definition (Claude Code / Codex)
├── _meta.json               # Marketplace metadata
├── README.md
├── .gitignore
├── scripts/
│   └── add_bookmarks.py     # Main script
└── references/
    └── dependencies.md      # Cross-platform dependency setup
```

## License

MIT
