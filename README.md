# PDF Add Bookmarks

Add hierarchical bookmarks/outline (章→节→小节) to PDF files. Supports both text-based and scanned (image-based) PDFs. For scanned PDFs, uses OCR to detect heading structure.

## Quick Start

```bash
pip install pypdf pymupdf pytesseract pillow
python scripts/add_bookmarks.py "input.pdf"
```

Output: `input_with_bookmarks.pdf`

## Features

- **Auto-detect** — Text-based or scanned PDF, Chinese or English headings
- **OCR support** — Automatically detects and OCRs scanned/image-based PDFs
- **Cross-platform** — Windows, macOS, Linux
- **TOC file mode** — Import bookmarks from a text table of contents
- **Content integrity** — Verifies original content is preserved

## Supported Heading Formats

| Language | Pattern | Example |
|----------|---------|---------|
| Chinese | `第X章 标题` | 第1章 概述 |
| Chinese | `X 标题` | 2 顺序表 |
| Chinese | `X.X 标题` | 2.1 背景 |
| Chinese | `X.X.X 标题` | 2.1.1 研究现状 |
| English | `X. Title` | 1. Introduction |
| English | `Chapter X` | Chapter 2 |
| English | `A.1. Title` | A.1. Classification |

## TOC File Mode

```bash
python scripts/add_bookmarks.py "input.pdf" --toc toc.txt [--offset N]
```

TOC format (indentation-based hierarchy):
```
第1章 概述 1
  1.1 背景 2
第2章 方法 15
```

## OCR Mode

```bash
python scripts/add_bookmarks.py "scanned.pdf" --force-ocr
```

Requires [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) with Chinese language data.

## Dependencies

- **Python**: `pypdf`, `pymupdf`, `pytesseract`, `pillow`
- **System**: `tesseract-ocr` (for scanned PDFs), `chi_sim` language pack

See `references/dependencies.md` for cross-platform installation guide.

## License

MIT
