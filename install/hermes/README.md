# PDF Add Bookmarks — Hermes Skill

## Installation

### Windows

```powershell
$skillsDir = "$env:LOCALAPPDATA\hermes\skills"
New-Item -ItemType Directory -Force -Path $skillsDir

# Clone or copy
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git "$skillsDir\pdf-add-bookmarks"

# Or copy from local project
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\SKILL.md" "$skillsDir\pdf-add-bookmarks\SKILL.md"
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\scripts" "$skillsDir\pdf-add-bookmarks\scripts"
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks\references" "$skillsDir\pdf-add-bookmarks\references"
```

### macOS

```bash
mkdir -p ~/Library/Application\ Support/hermes/skills
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git \
  ~/Library/Application\ Support/hermes/skills/pdf-add-bookmarks
```

### Linux

```bash
mkdir -p ~/.local/share/hermes/skills
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git \
  ~/.local/share/hermes/skills/pdf-add-bookmarks
```

## Configuration

Add the skill to your Hermes `config.yaml`. See `config.yaml` in this directory for the snippet.

## Usage

The skill triggers on keywords like:
- "add bookmarks to PDF"
- "PDF outline"
- "目录"
- "书签"

## Files

- `SKILL.md` — Hermes skill definition
- `config.yaml` — Example config snippet for Hermes `config.yaml`
- `README.md` — This file

## Prerequisites

- Python 3.9+
- `pip install pymupdf pytesseract pillow`
- Tesseract OCR with `chi_sim` language data

See main project `references/dependencies.md` for Tesseract setup.
