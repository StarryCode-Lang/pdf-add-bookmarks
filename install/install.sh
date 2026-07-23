#!/usr/bin/env bash
# Install PDF Add Bookmarks skill for all detected AI coding agents
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_NAME="pdf-add-bookmarks"

info()  { echo "  [..] $1"; }
ok()    { echo "  [OK] $1"; }
skip()  { echo "  [- ] $1"; }
err()   { echo "  [ERR] $1"; }

# === Python Dependencies ===
echo "=== Python Dependencies ==="
for pkg in pymupdf pytesseract pillow; do
    module="${pkg/-/_}"
    [ "$pkg" = "pymupdf" ] && module="fitz"
    python3 -c "import $module" 2>/dev/null || missing+=("$pkg")
done
if [ ${#missing[@]} -eq 0 ]; then
    ok "All Python packages already installed"
else
    pip3 install "${missing[@]}"
    ok "Python packages installed"
fi

# === Tesseract OCR ===
echo "=== Tesseract OCR ==="
if command -v tesseract >/dev/null 2>&1; then
    ok "Tesseract already installed"
    if tesseract --list-langs 2>&1 | grep -q chi_sim; then
        ok "Chinese language data found"
    else
        info "Installing Chinese language data..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install tesseract-lang
        elif command -v apt >/dev/null 2>&1; then
            sudo apt install -y tesseract-ocr-chi-sim
        fi
        ok "Chinese language data installed"
    fi
else
    err "Tesseract not found. Install it first:"
    echo "  macOS: brew install tesseract tesseract-lang"
    echo "  Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
    echo "  Fedora: sudo yum install tesseract"
fi

# === Agent Detection ===
detect_agent() {
    local name="$1" path="$2"
    if [ -d "$path" ]; then
        echo "  [OK] $name detected at $path"
        return 0
    else
        echo "  [- ] $name not found"
        return 1
    fi
}

echo "=== Detecting Installed Agents ==="
detect_agent "Claude Code" "$HOME/.claude" && CLAUDE=1 || CLAUDE=0
detect_agent "OpenCode" "$HOME/.config/opencode" && OPENCODE=1 || OPENCODE=0
detect_agent "Hermes" "$HOME/.local/share/hermes" && HERMES=1 || HERMES=0
detect_agent "OpenClaw" "$HOME/.config/openclaw" && OPENCLAW=1 || OPENCLAW=0
detect_agent "Kimi Code" "$HOME/.config/kimi-desktop" && KIMI=1 || KIMI=0

echo "=== Installing Skill ==="

install_skill() {
    local name="$1" target="$2" extra="$3"
    mkdir -p "$target/scripts"
    cp "$REPO_ROOT/SKILL.md" "$target/"
    cp "$REPO_ROOT/scripts/"*.py "$target/scripts/"
    [ -n "$extra" ] && cp "$REPO_ROOT/$extra" "$target/"
    ok "Installed for $name"
}

[ "$CLAUDE" -eq 1 ] && install_skill "Claude Code" "$HOME/.claude/plugins/$SCRIPT_NAME" ""
[ "$OPENCODE" -eq 1 ] && install_skill "OpenCode" "$HOME/.config/opencode/skills/$SCRIPT_NAME" "install/opencode/opencode-agent.json"
[ "$HERMES" -eq 1 ] && install_skill "Hermes" "$HOME/.local/share/hermes/skills/$SCRIPT_NAME" ""
[ "$OPENCLAW" -eq 1 ] && install_skill "OpenClaw" "$HOME/.config/openclaw/skills/$SCRIPT_NAME" ""
[ "$KIMI" -eq 1 ] && install_skill "Kimi Code" "$HOME/.config/kimi-desktop/plugins/$SCRIPT_NAME" ""

echo "=== Done ==="
echo "Usage: python3 scripts/add_bookmarks.py <input.pdf>"
