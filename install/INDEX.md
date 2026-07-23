# PDF Add Bookmarks — Multi-Agent Installation Index

## Overview

| Agent | Type | Install Location | Config File | Status |
|-------|------|-----------------|-------------|--------|
| [Claude Code](./claude-code/) | Plugin | `~/.claude/plugins/pdf-add-bookmarks/` | `plugin.json` | ✅ |
| [OpenCode](./opencode/) | Skill | `~/.config/opencode/skills/pdf-add-bookmarks/` | `opencode-agent.json` | ✅ |
| [Hermes](./hermes/) | Skill | `%LOCALAPPDATA%/hermes/skills/pdf-add-bookmarks/` | `SKILL.md` | ✅ |
| [OpenClaw](./openclaw/) | Skill | `%APPDATA%/OpenClawTray/skills/pdf-add-bookmarks/` | — | ✅ |
| [Kimi Code](./kimi-code/) | Plugin | `%APPDATA%/kimi-desktop/plugins/pdf-add-bookmarks/` | — | ✅ |
| [Manual](./manual/) | Any | Anywhere | — | ✅ |

## Quick Install

### Windows (PowerShell)

```powershell
# Auto-detect agents and install
.\install.ps1

# Or manually for a specific agent — see the subdirectory README.md
```

### macOS / Linux

```bash
chmod +x install.sh && ./install.sh
```

## What Gets Installed

Each agent config includes:
- **Triggers** that auto-activate the skill on keywords like "add bookmarks", "PDF outline", "书签", "目录"
- **Commands** to invoke bookmarking directly
- **Dependency info** for Python packages and Tesseract OCR

## Prerequisites

All install methods require:

1. **Python 3.9+** with pip
2. **Python packages**: `pymupdf`, `pytesseract`, `pillow`
3. **Tesseract OCR** with Chinese language data (`chi_sim`)

See [references/dependencies.md](../references/dependencies.md) for cross-platform setup.

## After Installation

Each agent will recognize requests like:
- "Add bookmarks to this PDF"
- "Create outline for thesis.pdf"
- "为这个PDF添加书签"
- "生成PDF目录"

## Updating

```bash
# Pull latest version and re-run installer
git pull && .\install.install.ps1  # Windows
# or
git pull && ./install/install.sh   # macOS/Linux
```
