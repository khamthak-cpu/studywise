# StudyWise continuity and uploads implementation

## What changed

- The frontend creates a backend conversation when the first message is sent and reuses its `conversation_id` for the rest of that chat.
- The `/ask` request now sends `conversation_id`, `student_id`, and optional attachment IDs.
- Follow-up questions of any length are accepted (including `Why?` and `Explain it.`).
- The model prompt explicitly preserves the current topic for follow-ups, resolves references, and allows natural topic changes.
- The backend sends up to 24 recent messages to the model.
- Added `POST /uploads` for PDF, PNG, JPG/JPEG, WEBP, DOCX and TXT uploads, with a 15 MB per-file limit, a five-file frontend limit, file signature checks, conversation ownership checks, and extraction of PDF/DOCX/TXT text.
- Image files are analyzed by a separately configured Ollama vision model. The resulting description is supplied to the text model as source context.
- The frontend has attachment chips, removal controls, upload errors, and a file picker.

## Setup

1. From `backend/`, install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Copy `backend/.env.example` to `backend/.env`. Keep `OLLAMA_HOST` and `LLM_MODEL` configured for your machine. `VISION_MODEL` defaults to `llava:7b`.

3. Pull the text and vision models in a terminal where Ollama is installed:

   ```bash
   ollama pull qwen3:4b
   ollama pull llava:7b
   ```

   If your computer cannot comfortably run both models, choose a smaller compatible vision model and set `VISION_MODEL` in `backend/.env`.

4. Start the API from the repository root (or use your existing backend launch command):

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. In another terminal, configure `frontend/.env` with:

   ```dotenv
   VITE_API_URL=http://localhost:8000
   VITE_USE_MOCK=false
   ```

6. Install frontend dependencies and run it:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Manual test checklist

1. Ask `Explain photosynthesis.`
2. Ask `Why is chlorophyll needed?` and confirm it answers about photosynthesis.
3. Ask `Give me three MCQs on it.` and confirm the questions stay on the same topic.
4. Ask an unrelated question, such as `Explain TCP vs UDP.` Confirm it answers the new topic without forcing photosynthesis into the answer.
5. Upload a text-based PDF and ask for its summary, then ask `Explain the second point.`
6. Upload a DOCX and TXT file and ask a question about their content.
7. Upload a clear PNG/JPG photo of a textbook question and ask it to solve/transcribe the question. Confirm Ollama has the configured vision model pulled.
8. Try an unsupported file, a zero-byte file, and a file larger than 15 MB; each should be rejected.
9. Start a new chat and verify it does not use attachments from the previous conversation.

## Important current limitations

- Scanned PDFs with no embedded text are detected as having no extractable text, but OCR is not included in this patch. Use text-based PDFs or add OCR (for example, Tesseract) for scanned documents.
- This implementation retains up to the latest 24 messages in model context. Very long conversations may need a persisted rolling summary to retain details older than that window.
- Image analysis runs through the configured vision model on each relevant request, so follow-ups involving images may be slower. A production version should cache image descriptions.
- This prototype uses the fixed demo student ID `demo-student` from the frontend. Add real authentication before exposing it to multiple users or the public internet.
- Uploaded files are stored locally in `data/uploads`; implement a retention/deletion policy and server-side request-size limits before production deployment.
- File content is checked against common file signatures, but this is not a substitute for malware scanning and hardened document processing in a public deployment.
