# PDF Add Bookmarks — Claude Code Plugin

## Quick Install

```powershell
# Windows
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git "$env:USERPROFILE\.claude\plugins\pdf-add-bookmarks"

# macOS / Linux
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git ~/.claude/plugins/pdf-add-bookmarks
```

## Usage

```
/pdf-add-bookmarks "document.pdf"
```

## Files

- `plugin.json` — Plugin manifest with metadata, commands, skills
- `CLAUDE.md` — Usage instructions for Claude Code
- `commands/` — Slash command definitions
- `agents/` — Agent definitions
- `skills/` — Skill definitions

## Prerequisites

- Python 3.9+, pip packages: `pymupdf pytesseract pillow`
- Tesseract OCR with `chi_sim` language data

See main project `references/dependencies.md` for setup details.
