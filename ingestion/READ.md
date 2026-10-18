# Rebuilding the index

1. Put NCERT PDFs in `data/raw/class{8-12}/{science|math|commerce|social_science}/chNN_title.pdf`
   (commerce is Class 11-12 only)
2. `ollama pull bge-m3`
3. From the project root: `python ingestion/build_index.py --extract --reset`
4. Spot-check: `python ingestion/chunk.py data/cleaned/class9/science/<file>.json`

Notes
- Page numbers are PDF page numbers, not the printed book numbers.
- If you change EMBED_MODEL in backend/.env you must re-run with --reset.
- Scanned PDFs (no text layer) print a warning and need OCR first.