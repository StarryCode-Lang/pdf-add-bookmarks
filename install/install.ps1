#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Install PDF Add Bookmarks skill for all detected AI coding agents.
.DESCRIPTION
    Auto-detects installed agents (Claude Code, OpenCode, Hermes, OpenClaw, Kimi Code)
    and installs the skill for each one. Also installs Python dependencies and Tesseract OCR.
#>

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScriptName = "pdf-add-bookmarks"

function Write-Step { param([string]$Msg) Write-Host "`n=== $Msg ===" -ForegroundColor Cyan }
function Write-OK { param([string]$Msg) Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Write-Skip { param([string]$Msg) Write-Host "  [- ] $Msg" -ForegroundColor Yellow }
function Write-Error { param([string]$Msg) Write-Host "  [ERR] $Msg" -ForegroundColor Red }

# === Install Python Dependencies ===
Write-Step "Python Dependencies"
$pkgs = @("pymupdf", "pytesseract", "pillow")
$missing = @()
foreach ($pkg in $pkgs) {
    try { python -c "import $($pkg -replace '-', '_' -replace '^(pymupdf)$', 'fitz')" 2>$null } catch { $missing += $pkg }
}
if ($missing.Count -eq 0) {
    Write-OK "All Python packages already installed"
} else {
    Write-Host "  Installing: $($missing -join ', ')"
    pip install $missing
    if ($LASTEXITCODE -eq 0) { Write-OK "Python packages installed" }
    else { Write-Error "Failed to install Python packages" }
}

# === Install Tesseract OCR ===
Write-Step "Tesseract OCR"
$tesseractPaths = @(
    "C:\Program Files\Tesseract-OCR\tesseract.exe",
    "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
)
$found = $false
foreach ($p in $tesseractPaths) { if (Test-Path $p) { $found = $true; break } }
if (-not $found) {
    # Try winget
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  Installing Tesseract via winget..."
        winget install UB-Mannheim.TesseractOCR
        if ($LASTEXITCODE -eq 0) { Write-OK "Tesseract installed" }
        else { Write-Error "Please install Tesseract manually from https://github.com/UB-Mannheim/tesseract/wiki" }
    } else {
        Write-Error "Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki"
    }
    # Check for Chinese language data
    $tessdata = "C:\Program Files\Tesseract-OCR\tessdata"
    if (Test-Path "$tessdata\chi_sim.traineddata") {
        Write-OK "Chinese language data found"
    } else {
        Write-Host "  Downloading Chinese language data..."
        mkdir -Force $tessdata >$null
        Invoke-WebRequest -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata" -OutFile "$tessdata\chi_sim.traineddata"
        Write-OK "Chinese language data installed"
    }
} else {
    Write-OK "Tesseract already installed"
}

# === Agent Detection & Installation ===
$userProfile = $env:USERPROFILE
$localAppData = $env:LOCALAPPDATA
$appData = $env:APPDATA

$agents = @(
    @{Name="Claude Code"; Path="$userProfile\.claude"; Check="plugins, skills"; Installed=$false}
    @{Name="OpenCode"; Path="$userProfile\.config\opencode"; Check="skills"; Installed=$false}
    @{Name="Hermes"; Path="$localAppData\hermes"; Check="skills"; Installed=$false}
    @{Name="OpenClaw"; Path="$appData\OpenClawTray"; Check="skills"; Installed=$false}
    @{Name="Kimi Code"; Path="$appData\kimi-desktop"; Check="plugins"; Installed=$false}
)

Write-Step "Detecting Installed Agents"
foreach ($agent in $agents) {
    if (Test-Path $agent.Path) {
        $agent.Installed = $true
        Write-OK "$($agent.Name) detected at $($agent.Path)"
    } else {
        Write-Skip "$($agent.Name) not found"
    }
}

Write-Step "Installing Skill for Detected Agents"

# Claude Code
if ($agents[0].Installed) {
    $target = "$($agents[0].Path)\plugins\$ScriptName"
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Force -Path "$($agents[0].Path)\skills\$ScriptName\scripts" >$null
        Copy-Item "$RepoRoot\SKILL.md" "$($agents[0].Path)\skills\$ScriptName\"
        Copy-Item "$RepoRoot\scripts\*" "$($agents[0].Path)\skills\$ScriptName\scripts\"
        Copy-Item "$RepoRoot\references" "$($agents[0].Path)\skills\$ScriptName\references\" -Recurse
        Write-OK "Installed for Claude Code"
    } else { Write-OK "Already installed for Claude Code" }
}

# OpenCode
if ($agents[1].Installed) {
    $target = "$($agents[1].Path)\skills\$ScriptName"
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Force -Path $target >$null
        Copy-Item "$RepoRoot\SKILL.md" "$target\"
        Copy-Item "$RepoRoot\scripts" "$target\scripts\" -Recurse
        Copy-Item "$RepoRoot\install\opencode\opencode-agent.json" "$target\"
        Write-OK "Installed for OpenCode"
    } else { Write-OK "Already installed for OpenCode" }
}

# Hermes
if ($agents[2].Installed) {
    $target = "$($agents[2].Path)\skills\$ScriptName"
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Force -Path $target >$null
        Copy-Item "$RepoRoot\install\hermes\SKILL.md" "$target\"
        Copy-Item "$RepoRoot\scripts" "$target\scripts\" -Recurse
        Copy-Item "$RepoRoot\references" "$target\references\" -Recurse
        Write-OK "Installed for Hermes"
    } else { Write-OK "Already installed for Hermes" }
}

# OpenClaw
if ($agents[3].Installed) {
    $target = "$($agents[3].Path)\skills\$ScriptName"
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Force -Path $target >$null
        Copy-Item "$RepoRoot\SKILL.md" "$target\"
        Copy-Item "$RepoRoot\scripts" "$target\scripts\" -Recurse
        Write-OK "Installed for OpenClaw"
    } else { Write-OK "Already installed for OpenClaw" }
}

# Kimi Code
if ($agents[4].Installed) {
    $target = "$($agents[4].Path)\plugins\$ScriptName"
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Force -Path $target >$null
        Copy-Item "$RepoRoot\SKILL.md" "$target\"
        Copy-Item "$RepoRoot\scripts" "$target\scripts\" -Recurse
        Write-OK "Installed for Kimi Code"
    } else { Write-OK "Already installed for Kimi Code" }
}

Write-Step "Installation Complete"
Write-Host "Usage: python scripts/add_bookmarks.py <input.pdf>" -ForegroundColor Green
Write-Host "See $RepoRoot\README.md for full documentation." -ForegroundColor Gray
