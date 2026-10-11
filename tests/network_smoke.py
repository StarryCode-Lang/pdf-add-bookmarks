from pathlib import Path
import sys, subprocess, hashlib, json
import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import add_bookmarks as app


def main():
    directory = ROOT / "validation"
    directory.mkdir(exist_ok=True)
    sources = {
        "text": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "scan2": "https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/linn.pdf",
    }
    rows = []
    for name, url in sources.items():
        source = directory / (name + ".pdf")
        if not source.exists():
            import urllib.request
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(1_000_001)
            if len(data) > 1_000_000 or not data.startswith(b"%PDF"):
                raise ValueError("Network sample is not a small PDF")
            source.write_bytes(data)
        output = directory / (name + "_with_bookmarks.pdf")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/add_bookmarks.py"), str(source),
                                 "--lang", "eng", "--workers", "1", "-o", str(output)],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        with fitz.open(source) as doc:
            lengths = [len(page.get_text().strip()) for page in doc]
            pages = len(doc)
        with fitz.open(output) as doc:
            toc = doc.get_toc()
            assert toc and all(1 <= row[2] <= len(doc) for row in toc)
            if name == "text":
                assert toc == [[1, "Dummy PDF file", 1]]
            else:
                assert lengths == [0]
                assert "OCR required for 1/1 pages" in result.stdout
                assert any(row[1] == "Recording a Sequence" for row in toc)
                assert any(row[1] == "The LinnSequencer" for row in toc)
        assert app.verify_content(source, output)
        rows.append(dict(name=name, url=url, bytes=source.stat().st_size, pages=pages,
                         extractable_text_lengths=lengths, bookmark_count=len(toc),
                         input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                         all_page_pixels_and_text_equal=True))
    data = dict(python=sys.version, pymupdf=fitz.VersionBind,
                source_sha256=hashlib.sha256((ROOT / "scripts/add_bookmarks.py").read_bytes()).hexdigest(),
                results=rows)
    (directory / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
