"""Optional, source-pinned full-book benchmark; binaries/evidence stay in validation/."""
from pathlib import Path
import sys, hashlib, json, re, time, urllib.request
import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import add_bookmarks as app

SOURCES = {
    'text': ('https://greenteapress.com/thinkpython2/thinkpython2.pdf', '6033000bac3f9268ad75ee041bf8e5d9a3bc8a33bb156399cbd014918cb59f94'),
    'scan': ('https://archive.org/download/CalculusMadeEasy/Calculus_Made_Easy_Thompson.pdf', 'a3fb238d8710d78306ab99435ed8aa0c5353586dd69725ebe690bcfecdeb985b'),
}
# Independently transcribed from the printed contents, pp. ix-x; PDF offset +14.
SCAN_CHAPTER_PAGES = [15, 17, 23, 32, 40, 49, 63, 66, 81, 90, 107, 126,
                      135, 148, 179, 189, 196, 205, 220, 240, 248, 263, 280]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(title):
    title = re.sub(r'^(Chapter|Part|Appendix)\s+(\d+|[A-Z]+)\.?\s+|^\d+(?:\.\d+)*\.?\s+|^[A-Z]\.\d+\s+', '', title, flags=re.I)
    return re.sub(r'\W', '', title).lower()


def main():
    directory = ROOT / 'validation'
    directory.mkdir(exist_ok=True)
    rows = []
    for name, (url, expected_hash) in SOURCES.items():
        original = directory / (name + '-original.pdf')
        if not original.exists():
            with urllib.request.urlopen(url, timeout=120) as response, original.open('wb') as file:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 50 * 1024 * 1024:
                        raise ValueError('Sample exceeds 50 MiB')
                    file.write(chunk)
        if expected_hash and digest(original) != expected_hash:
            raise ValueError('Source changed; review reference before updating its hash')
        source = directory / (name + '.pdf')
        with fitz.open(original) as doc:
            reference = doc.get_toc()
            assert len(doc) >= 100
            original_outline_count = len(reference)
            if name == 'text':
                assert reference, 'Publisher outline is required as independent reference'
                doc.set_toc([])  # No outline is available to the recognition algorithm.
                doc.save(source)
            else:
                assert not reference and all(not p.get_text().strip() for p in doc)
                source.write_bytes(original.read_bytes())
        with fitz.open(source) as doc:
            assert not doc.get_toc()
        started = time.perf_counter()
        # Cache only benchmark OCR evidence, keyed by implementation and original bytes.
        cache = directory / (name + '-pages.json')
        key = digest(ROOT / 'scripts/add_bookmarks.py') + digest(source)
        cached = json.loads(cache.read_text()) if cache.exists() else {}
        if cached.get('key') == key:
            pages, scanned, visual = cached['pages'], set(cached['scanned']), {int(k): v for k, v in cached['visual'].items()}
            recognition_seconds = cached['recognition_seconds']
        else:
            pages, scanned, visual = app.read_pages(str(source), lang='eng', workers=4, dpi=200)
            recognition_seconds = time.perf_counter() - started
            cache.write_text(json.dumps(dict(key=key, pages=pages, scanned=sorted(scanned),
                                            visual=visual, recognition_seconds=recognition_seconds)), encoding='utf-8')
        headings = app.headings_from_pages(pages, scanned, visual=visual)
        output = directory / (name + '_with_bookmarks.pdf')
        app.add_bookmarks(source, app.build_tree_from_headings(headings), output, 'full')
        with fitz.open(output) as doc:
            toc = doc.get_toc()
            assert toc and all(1 <= row[2] <= len(doc) for row in toc)
        if name == 'text':
            expected = {(level, normalize(title), page) for level, title, page in reference}
            actual = {(level, normalize(title), page) for level, title, page in toc}
            matched = expected & actual
            missing = sorted(expected - actual)
            extras = sorted(actual - expected)
            assert not missing, missing
            metrics = dict(reference_entries=len(expected), matched_title_page_level=len(matched),
                           reference_recall=len(matched) / len(expected),
                           additional_candidates=extras)
        else:
            found = {h['page'] for h in headings if re.match(r'^CHAPTER\s+[A-Z]+\b', h['title'], re.I)}
            expected = set(SCAN_CHAPTER_PAGES)
            missing = sorted(expected - found)
            extra = sorted(found - expected)
            assert not missing and not extra, (missing, extra)
            assert len(scanned) == len(pages)
            metrics = dict(reference_chapters=len(expected), correct_chapter_pages=len(found & expected),
                           chapter_page_recall=len(found & expected) / len(expected),
                           unexpected_chapter_pages=extra,
                           note='Chapter destinations only; OCR wording and all extra headings require review')
        rows.append(dict(name=name, url=url, pages=len(pages), original_outline_count=original_outline_count,
                         input_outline_count=0, ocr_pages=len(scanned), bookmarks=len(toc),
                         original_sha256=digest(original), input_sha256=digest(source), output_sha256=digest(output),
                         recognition_seconds=round(recognition_seconds, 2),
                         save_and_full_verification_seconds=round(time.perf_counter() - started - (0 if cached.get('key') == key else recognition_seconds), 2),
                         all_page_pixels_text_streams_navigation_preserved=True, metrics=metrics, toc=toc))
    results = dict(python=sys.version, pymupdf=fitz.VersionBind,
                   implementation_sha256=digest(ROOT / 'scripts/add_bookmarks.py'), results=rows)
    (directory / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{k: v for k, v in row.items() if k != 'toc'} for row in rows], indent=2))


if __name__ == '__main__':
    main()
