# StudyWise — local development

## Prerequisites
- Python 3.11 or 3.12
- Node.js 20+
- Ollama installed and running
- The configured chat and embedding models pulled in Ollama (`qwen3:4b` and `bge-m3`)
- The ChromaDB index in `data/chroma_db` built with the same embedding model configured by `EMBED_MODEL`

Before starting the backend, run `ollama pull qwen3:4b` and `ollama pull bge-m3`, and make sure Ollama is running.

## Backend (Windows PowerShell)
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit backend/.env if your Ollama host/models differ.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Backend (macOS/Linux)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: open `http://127.0.0.1:8000/health`. A `degraded` status means a model, Ollama, or the index is unavailable.

**Build the local RAG index:** this project includes cleaned sample textbook data for Class 9 Mathematics, Science, and Social Science under `data/cleaned/`. Run `python ingestion/build_index.py --reset` from the project root to create the ChromaDB index using the configured local Ollama embedding model (`bge-m3`). No API key or extra PDF is needed to test the included data. To add more books later, place PDFs under `data/raw/class{8-12}/...` and run `python ingestion/build_index.py --extract --reset`. Until indexing is complete, `/health` reports a degraded index and `/ask` returns HTTP 503.

## Frontend
In another terminal:
```bash
cd frontend
npm ci
```
Optional: copy `.env.example` to `.env.local`. The frontend now connects to the backend by default; set `VITE_USE_MOCK=true` only if you deliberately want sample/demo answers. Then run:
```bash
npm run dev
```
Open the Vite URL shown in the terminal (normally `http://localhost:5173`).

To use the UI without a working backend, set `VITE_USE_MOCK=true`; sample answers are demo-only and do not validate backend functionality.

## Notes
- Never commit `.env`, API keys, local virtual environments, or `node_modules`.
- The ChromaDB index is generated locally from `data/cleaned/`; it is intentionally not bundled in this source archive. Rebuild it if you change `EMBED_MODEL`.
- `GET /health` reports readiness of Ollama models and the vector index; internet availability is informational and does not guarantee that web search succeeds.

## Backend tests

Run the backend test suite from the `backend` directory. Tests use a mocked local LLM and temporary SQLite storage where practical; they do not require a running Ollama server or access to student data.

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
```

The suite covers API validation and response shapes, upload validation and ownership checks, document text extraction, and LLM success/error handling. These are regression tests, not a substitute for a small manual integration check against your installed Ollama models.
