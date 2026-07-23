# PDF Add Bookmarks — OpenCode Skill

## Installation

### Windows

```powershell
# Create skills directory if not exists
$skillsDir = "$env:USERPROFILE\.config\opencode\skills"
New-Item -ItemType Directory -Force -Path $skillsDir

# Clone or copy the skill
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git "$skillsDir\pdf-add-bookmarks"

# Or copy from local project
Copy-Item -Recurse "D:\Desktop\pdf-add-bookmarks" "$skillsDir\pdf-add-bookmarks"
```

### macOS / Linux

```bash
mkdir -p ~/.config/opencode/skills
git clone https://github.com/StarryCode-Lang/pdf-add-bookmarks.git \
  ~/.config/opencode/skills/pdf-add-bookmarks
```

## Usage

In OpenCode, the skill auto-triggers on keywords like:
- "add bookmarks to PDF"
- "PDF outline"
- "目录"
- "书签"

Or invoke directly via the agent system.

## Files

- `opencode-agent.json` — Agent definition with triggers and commands
- `README.md` — This file

## Prerequisites

- Python 3.9+
- `pip install pymupdf pytesseract pillow`
- Tesseract OCR with `chi_sim` language data

See main project `references/dependencies.md` for Tesseract setup.
