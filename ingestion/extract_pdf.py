"""PDF -> cleaned paragraphs with page numbers (data/cleaned/**.json)."""
import argparse
import json
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned"
SUBJECTS = {"science", "math", "commerce", "social_science"}
EDGE = 0.065  # top/bottom fraction of a page treated as header/footer zone

REPRINT_RE = re.compile(r"reprint\s*20\d\d", re.I)
PAGE_NO_RE = re.compile(r"\d{1,3}")
CHAPTER_RE = re.compile(r"ch(?:apter)?[_\- ]?(\d+)[_\- ]*(.*)", re.I)


def parse_location(pdf: Path) -> tuple[int, str] | None:
    parts = pdf.relative_to(RAW).parts  # class9/science/file.pdf
    if len(parts) != 3:
        return None
    m = re.fullmatch(r"class[_\- ]?(\d{1,2})", parts[0], re.I)
    subject = parts[1].lower()
    if not m or subject not in SUBJECTS or not 8 <= int(m[1]) <= 12:
        return None
    if subject == "commerce" and int(m[1]) < 11:
        return None
    return int(m[1]), subject


def chapter_title(stem: str) -> str:
    pretty = lambda s: re.sub(r"[_\-]+", " ", s).strip().title()
    m = CHAPTER_RE.fullmatch(stem)
    if not m:
        return pretty(stem)
    title = pretty(m[2])
    return f"Chapter {int(m[1])}: {title}" if title else f"Chapter {int(m[1])}"


def clean_block(text: str) -> str:
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # re-join hyphenated line breaks
    text = unicodedata.normalize("NFC", text)             # NFC keeps ², ½ etc. intact (NFKC would not)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\u00ad\u200b]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf(pdf: Path) -> dict | None:
    loc = parse_location(pdf)
    if loc is None:
        print(f"  SKIP {pdf.relative_to(RAW)}: expected class{{8-12}}/{{subject}}/file.pdf")
        return None
    class_level, subject = loc

    pages, empty = [], 0
    with fitz.open(pdf) as doc:
        total = doc.page_count
        for i, page in enumerate(doc, start=1):
            h = page.rect.height
            paras = []
            for b in page.get_text("blocks", sort=True):
                y0, y1, raw, btype = b[1], b[3], b[4], b[6]
                if btype != 0:  # skip images
                    continue
                text = clean_block(raw)
                if not text or REPRINT_RE.search(text):
                    continue
                in_edge = y1 < EDGE * h or y0 > (1 - EDGE) * h
                if in_edge and (len(text) < 80 or PAGE_NO_RE.fullmatch(text)):
                    continue  # running header / footer / page number
                paras.append(text)
            if sum(map(len, paras)) < 30:
                empty += 1
            if paras:
                pages.append({"page": i, "paragraphs": paras})

    if empty > max(2, total * 0.5):
        print(f"  WARN {pdf.name}: {empty}/{total} pages have almost no text. Scanned PDF? Needs OCR.")

    return {
        "source": pdf.relative_to(RAW).with_suffix("").as_posix(),
        "class_level": class_level,
        "subject": subject,
        "chapter": chapter_title(pdf.stem),
        "pages": pages,
    }


def extract_all(force: bool = False) -> int:
    done = 0
    for pdf in sorted(RAW.rglob("*.pdf")):
        out = CLEAN / pdf.relative_to(RAW).with_suffix(".json")
        if out.exists() and not force and out.stat().st_mtime > pdf.stat().st_mtime:
            continue
        doc = extract_pdf(pdf)
        if doc is None:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        n_para = sum(len(p["paragraphs"]) for p in doc["pages"])
        print(f"  OK   {doc['source']}: {len(doc['pages'])} pages, {n_para} paragraphs")
        done += 1
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-extract even if up to date")
    args = ap.parse_args()
    print(f"Extracted {extract_all(args.force)} file(s)")