# PDF Add Bookmarks — Manual Installation

For any agent not listed in the other install directories, use this manual approach.

## Quick Start

### 1. Install Python Dependencies

```bash
pip install pymupdf pytesseract pillow
```

### 2. Install Tesseract OCR

**Windows:**
```powershell
winget install UB-Mannheim.TesseractOCR
# Then add to PATH: C:\Program Files\Tesseract-OCR\
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

### 3. Use the Script

```bash
# Navigate to the project directory
cd D:\Desktop\pdf-add-bookmarks

# Basic usage - auto-detect mode
python scripts/add_bookmarks.py "input.pdf"

# Output: input_with_bookmarks.pdf

# Or copy scripts to anywhere and run
python add_bookmarks.py "document.pdf"
```

### 4. Add to PATH (Optional)

**Windows PowerShell:**
```powershell
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$scriptDir = "D:\Desktop\pdf-add-bookmarks\scripts"
if ($userPath -notlike "*$scriptDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$scriptDir", "User")
}
```

**macOS / Linux (add to ~/.zshrc or ~/.bashrc):**
```bash
export PATH="$PATH:/path/to/pdf-add-bookmarks/scripts"
```

Then run from anywhere:
```bash
add_bookmarks.py "document.pdf"
```

## All Usage Modes

```bash
# Auto-detect (textbook/exam/slides/article)
python add_bookmarks.py input.pdf

# Analyze PDF content first (OCR all pages, show summary)
python add_bookmarks.py input.pdf --analyze

# Auto-generate TOC then add bookmarks
python add_bookmarks.py input.pdf --generate-toc

# TOC file mode
python add_bookmarks.py input.pdf --toc toc.txt

# Force OCR for scanned PDFs
python add_bookmarks.py input.pdf --force-ocr

# Custom output path
python add_bookmarks.py input.pdf -o output.pdf
```

## Integration with Any Agent

Tell your agent: "Use the PDF Add Bookmarks skill at [path] to add hierarchical bookmarks to PDF files."

The script supports these operations:
- **Auto-detect** PDF type (textbook/exam/slides/article)
- **Extract headings** from text-based PDFs
- **OCR** scanned/image-based PDFs
- **Smart fallback** when no headings found
- **TOC file import** with indentation hierarchy
