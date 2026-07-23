# PDF Add Bookmarks — OpenClaw Skill

## Installation

### Windows

```powershell
# Create skills directory
$skillsDir = "$env:APPDATA\OpenClawTray\skills"
New-Item -ItemType Directory -Force -Path $skillsDir

# Clone or copy
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git "$skillsDir\pdf-add-bookmarks"
```

Or copy from local project:
```powershell
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks" "$skillsDir\pdf-add-bookmarks"
```

### macOS / Linux

```bash
mkdir -p ~/.config/openclaw/skills
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git \
  ~/.config/openclaw/skills/pdf-add-bookmarks
```

## Usage

Once installed, OpenClaw will recognize the skill when you say:
- "add bookmarks to PDF"
- "PDF outline / 目录 / 书签"
- "add outline to document.pdf"

Or run directly:
```bash
python scripts/add_bookmarks.py "input.pdf"
```

## Prerequisites

- Python 3.9+
- `pip install pymupdf pytesseract pillow`
- Tesseract OCR with `chi_sim` language data

See main project `references/dependencies.md` for Tesseract setup.
