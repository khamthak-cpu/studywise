
from pathlib import Path

# Project root: D:\studywise
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = PROJECT_ROOT / "data" / "raw"


def find_textbooks():
    if not RAW_DATA.exists():
        raise FileNotFoundError(
            f"Raw data folder not found: {RAW_DATA}"
        )

    for pdf_path in sorted(RAW_DATA.rglob("*")):
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            continue

        relative_path = pdf_path.relative_to(RAW_DATA)
        parts = relative_path.parts

        school_class = parts[0] if len(parts) >= 2 else "unknown"
        subject = parts[1] if len(parts) >= 2 else "unknown"

        yield {
            "path": pdf_path,
            "class": school_class,
            "subject": subject,
            "filename": pdf_path.name,
        }


if __name__ == "__main__":
    books = list(find_textbooks())

    if not books:
        print(f"No PDF files found in: {RAW_DATA}")

    for book in books:
        print(
            f"Found: {book['filename']} | "
            f"Class: {book['class']} | "
            f"Subject: {book['subject']} | "
            f"Path: {book['path']}"
        )

    print(f"\nTotal PDFs found: {len(books)}")
