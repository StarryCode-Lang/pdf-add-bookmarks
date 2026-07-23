# PDF Add Bookmarks — Claude Code Plugin

> Add hierarchical bookmarks to PDFs directly from Claude Code.

## Installation

### Option A: Clone to Claude Code plugins directory

```bash
# Windows (PowerShell)
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git \
  "$env:USERPROFILE\.claude\plugins\pdf-add-bookmarks"

# macOS / Linux
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git \
  ~/.claude/plugins/pdf-add-bookmarks
```

### Option B: Symlink for development

```powershell
# Windows (PowerShell, admin)
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\plugins\pdf-add-bookmarks" `
  -Target "D:\Desktop\pdf-add-bookmarks"

# macOS / Linux
ln -s /path/to/pdf-add-bookmarks ~/.claude/plugins/pdf-add-bookmarks
```

### Option C: Copy skill files only

```powershell
# Windows
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\SKILL.md" `
  "$env:USERPROFILE\.claude\skills\pdf-add-bookmarks\SKILL.md"
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\scripts" `
  "$env:USERPROFILE\.claude\skills\pdf-add-bookmarks\scripts"
```

## Usage

After installation, use the slash command in Claude Code:

```
/pdf-add-bookmarks "document.pdf"
```

### Supported options

| Option | Description |
|--------|-------------|
| `--output` | Output file path (default: `*_with_bookmarks.pdf`) |
| `--toc` | Import bookmarks from a TOC text file |
| `--force-ocr` | Force OCR mode for scanned PDFs |
| `--lang` | Tesseract language (default: `chi_sim+eng`) |

### Examples

```
/pdf-add-bookmarks "thesis.pdf"
/pdf-add-bookmarks "scanned_book.pdf" --force-ocr
/pdf-add-bookmarks "textbook.pdf" --toc "toc.txt" --offset 2
```

## Prerequisites

- Python 3.9+
- `pip install pymupdf pytesseract pillow`
- Tesseract OCR with Chinese language data (`chi_sim`)

See `references/dependencies.md` for cross-platform Tesseract setup.

## Plugin Structure

```
claude-code/
├── plugin.json      # Plugin manifest
├── CLAUDE.md        # This file
├── commands/        # Slash command definitions
├── agents/          # Agent definitions
└── skills/          # Skill definitions
```

## Troubleshooting

**Tesseract not found:**
- Windows: Ensure `C:\Program Files\Tesseract-OCR\` is in PATH
- macOS: `brew install tesseract tesseract-lang`
- Linux: `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`

**Chinese headings not recognized:**
Verify `chi_sim` is installed: `pytesseract.get_languages()`

## License

MIT
