# PDF Add Bookmarks — Kimi Code Plugin

## Installation

### Windows

```powershell
# Create plugin directory
$pluginDir = "$env:APPDATA\kimi-desktop\plugins\pdf-add-bookmarks"
New-Item -ItemType Directory -Force -Path $pluginDir

# Copy skill files
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\SKILL.md" "$pluginDir\"
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\scripts" "$pluginDir\scripts"
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\references" "$pluginDir\references"
```

### macOS

```bash
mkdir -p ~/Library/Application\ Support/kimi-desktop/plugins/pdf-add-bookmarks
cp -r /path/to/pdf-add-bookmarks/SKILL.md ~/Library/Application\ Support/kimi-desktop/plugins/pdf-add-bookmarks/
cp -r /path/to/pdf-add-bookmarks/scripts ~/Library/Application\ Support/kimi-desktop/plugins/pdf-add-bookmarks/
```

## Usage

In Kimi Code, invoke via skill trigger keywords:
- "add bookmarks to PDF"
- "PDF outline / 目录 / 书签"
- "为PDF添加书签"
- "PDF大纲"

Or call the script directly:
```bash
python scripts/add_bookmarks.py "input.pdf"
```

## Supported Options

| Flag | Description |
|------|-------------|
| `-o, --output` | Output PDF path |
| `--toc` | Import bookmarks from TOC file |
| `--force-ocr` | Force OCR mode |
| `--analyze` | Analyze PDF content and generate suggested TOC |
| `--generate-toc` | Auto-generate TOC then add bookmarks |
| `--lang` | Tesseract language (default: chi_sim+eng) |

## Prerequisites

- Python 3.9+
- `pip install pymupdf pytesseract pillow`
- Tesseract OCR with `chi_sim` language data

See main project `references/dependencies.md` for Tesseract setup.
