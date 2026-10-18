"""Embed chunks and store them in ChromaDB. Safe to re-run (idempotent per source file).

    python ingestion/build_index.py --extract        # extract PDFs first, then index
    python ingestion/build_index.py --reset          # wipe collection and rebuild everything
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import chromadb
from ollama import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings  # noqa: E402  same model/collection/path as the API
from chunk import chunk_document  # noqa: E402
from extract_pdf import CLEAN, extract_all  # noqa: E402


def embed_text(c: dict) -> str:
    # chapter/section context makes short chunks much easier to retrieve
    return f"{c['chapter']} | {c['section']}\n{c['text']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true", help="run PDF extraction first")
    ap.add_argument("--reset", action="store_true", help="delete the collection before indexing")
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    cfg = get_settings()
    if args.extract:
        extract_all()

    files = sorted(CLEAN.rglob("*.json"))
    if not files:
        sys.exit("No cleaned files. Put PDFs in data/raw/ and run with --extract.")

    ollama = Client(host=cfg.ollama_host, timeout=cfg.llm_timeout_s)
    db = chromadb.PersistentClient(path=str(cfg.chroma_path))
    if args.reset:
        try:
            db.delete_collection(cfg.collection)
        except Exception:
            pass
    col = db.get_or_create_collection(cfg.collection, metadata={"hnsw:space": "cosine"})

    stats: Counter = Counter()
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        chunks = chunk_document(doc)
        if not chunks:
            print(f"  EMPTY {doc['source']}")
            continue
        col.delete(where={"source": doc["source"]})  # drop stale chunks of this file
        for i in range(0, len(chunks), args.batch):
            part = chunks[i:i + args.batch]
            embs = ollama.embed(model=cfg.embed_model, input=[embed_text(c) for c in part]).embeddings
            col.upsert(
                ids=[c["id"] for c in part],
                embeddings=embs,
                documents=[c["text"] for c in part],
                metadatas=[{k: c[k] for k in ("chapter", "section", "page", "subject", "class_level", "source")}
                           for c in part],
            )
        stats[(doc["class_level"], doc["subject"])] += len(chunks)
        print(f"  OK   {doc['source']}: {len(chunks)} chunks")

    print("\nChunks per class/subject:")
    for (cl, sub), n in sorted(stats.items()):
        print(f"  Class {cl:>2} {sub:<15} {n}")
    print(f"\nCollection '{cfg.collection}' now holds {col.count()} chunks (model: {cfg.embed_model})")


if __name__ == "__main__":
    main()