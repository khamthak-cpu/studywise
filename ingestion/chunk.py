"""Section-aware chunking. Keeps worked examples/activities together, adds chapter/section/page metadata."""
import json
import re
import sys

MAX_CHARS = 1200      # normal chunk size
ATOMIC_MAX = 2000     # Examples / Activities may grow bigger so a problem stays with its solution
MIN_CHARS = 120       # shorter pieces (lone headings) merge into the next chunk
OVERLAP = 150

SECTION_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2}){1,3}\s+\S")      # "1.2 Laws of Motion"
ATOMIC_RE = re.compile(r"^(Example|Activity|Experiment)\s*\d", re.I)
SENT_RE = re.compile(r"(?<=[.!?।])\s+")


def split_long(text: str, limit: int = MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for s in SENT_RE.split(text):
        while len(s) > limit:  # pathological run-on text
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[:limit])
            s = s[limit:]
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_document(doc: dict) -> list[dict]:
    units = [(p["page"], t) for p in doc["pages"] for t in p["paragraphs"]]
    chunks: list[dict] = []
    buf: list[str] = []
    size, page0, sec0, section, atomic = 0, None, "", "", False

    def emit(overlap: bool = False, force: bool = False) -> bool:
        nonlocal buf, size
        text = "\n".join(buf).strip()
        if not text:
            buf, size = [], 0
            return False
        if len(text) < MIN_CHARS and not force:
            return False  # keep accumulating
        chunks.append({
            "id": f"{doc['source']}#{len(chunks):04d}",
            "text": text,
            "chapter": doc["chapter"],
            "section": sec0[:120],
            "page": page0,
            "subject": doc["subject"],
            "class_level": doc["class_level"],
            "source": doc["source"],
        })
        carry, n = [], 0
        if overlap:
            for p in reversed(buf):
                if n + len(p) > OVERLAP:
                    break
                carry.insert(0, p)
                n += len(p)
        buf, size = carry, n
        return True

    for page, para in units:
        is_sec = len(para) < 120 and SECTION_RE.match(para)
        is_atomic = ATOMIC_RE.match(para)
        if is_sec or is_atomic:
            emit()
            if is_sec:
                section = para
            if not buf:
                page0, sec0 = page, section
            elif is_sec:
                sec0 = section
            buf.append(para)
            size += len(para)
            atomic = bool(is_atomic)
            continue
        for piece in split_long(para):
            if buf and size + len(piece) > (ATOMIC_MAX if atomic else MAX_CHARS):
                if emit(overlap=True):
                    page0, sec0 = page, section
            if not buf:
                page0, sec0 = page, section
            buf.append(piece)
            size += len(piece)
    emit(force=True)
    return chunks


if __name__ == "__main__":  # preview: python ingestion/chunk.py data/cleaned/class9/science/ch01_x.json
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    cs = chunk_document(d)
    sizes = [len(c["text"]) for c in cs]
    print(f"{len(cs)} chunks | avg {sum(sizes)//max(1,len(sizes))} chars | max {max(sizes, default=0)}")
    for c in cs[:3]:
        print(f"\n--- {c['id']} | p.{c['page']} | {c['section']}\n{c['text'][:400]}")