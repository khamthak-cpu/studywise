"""Check data/raw before ingestion:  python ingestion/check_data.py"""
import re
from collections import Counter
from pathlib import Path

import pymupdf as fitz # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SUBJECTS = {"science", "math", "commerce", "social_science"}
NAME_RE = re.compile(r"ch(?:apter)?[_\- ]?\d+[_\- ]*.*", re.I)


def problem_with(pdf: Path) -> str | None:
    parts = pdf.relative_to(RAW).parts
    if len(parts) != 3:
        return "must sit in class<N>/<subject>/file.pdf"
    m = re.fullmatch(r"class[_\- ]?(\d{1,2})", parts[0], re.I)
    if not m or not 8 <= int(m[1]) <= 12:
        return f"folder '{parts[0]}' must be class8 ... class12"
    subject = parts[1].lower()
    if subject not in SUBJECTS:
        return f"subject folder '{parts[1]}' must be one of {sorted(SUBJECTS)}"
    if subject == "commerce" and int(m[1]) < 11:
        return "commerce is for class 11-12 only"

def has_text_layer(pdf: Path, sample: int = 3) -> bool:
    try:
        with fitz.open(pdf) as doc:
            pages = [doc[i] for i in range(min(sample, doc.page_count))]
            return sum(len(p.get_text().strip()) for p in pages) > 100
    except Exception:
        return False


def main() -> None:
    pdfs = sorted(RAW.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {RAW}")
        return
    counts: Counter = Counter()
    bad = scanned = 0
    for pdf in pdfs:
        rel = pdf.relative_to(RAW)
        issue = problem_with(pdf)
        if issue:
            bad += 1
            print(f"  BAD     {rel}: {issue}")
            continue
        if not has_text_layer(pdf):
            scanned += 1
            print(f"  SCANNED {rel}: no text layer found, needs OCR")
        counts[(rel.parts[0], rel.parts[1])] += 1
    print("\nPDFs per class/subject:")
    for (c, s), n in sorted(counts.items()):
        print(f"  {c:<8} {s:<15} {n}")
    print(f"\n{len(pdfs)} PDFs | {bad} badly named/placed | {scanned} look scanned")


if __name__ == "__main__":
    main()