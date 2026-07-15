# Cross-Platform Dependency Setup

## Python Packages

```bash
pip install pymupdf pytesseract pillow
```

## Tesseract OCR

### Windows
```powershell
winget install UB-Mannheim.TesseractOCR
```
Add to PATH: `C:\Program Files\Tesseract-OCR\`

### macOS
```bash
brew install tesseract
```

### Linux (Debian/Ubuntu)
```bash
sudo apt install tesseract-ocr
```

### Linux (RHEL/Fedora)
```bash
sudo yum install tesseract
```

## Chinese Language Data (chi_sim)

### Windows
Download `chi_sim.traineddata` from https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata
Place in `C:\Program Files\Tesseract-OCR\tessdata\`

### macOS
```bash
brew install tesseract-lang
```

### Linux (Debian/Ubuntu)
```bash
sudo apt install tesseract-ocr-chi-sim
```

## Verify Installation

```python
import pytesseract
print(pytesseract.get_languages())
# Should include 'chi_sim' and 'eng'
```