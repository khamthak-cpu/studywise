# Studywise — AI Study Assistant frontend

React + TypeScript + Vite frontend for the AI Study Assistant hackathon prototype.

## Features

- Responsive chat UI with starter prompts
- Mock mode so frontend work can continue before the backend is ready
- API client for `POST /ask` and `GET /health`
- Source citations and grounded/uncertain badges
- Standard/simple explanation controls and English/Hindi selector
- Loading, error, recent-conversation, and backend-status UI

## Requirements

- Node.js 20+ recommended
- npm

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

The default `.env` behavior is mock mode. Copy `.env.example` to `.env` if you want to change settings.

## Connect your teammate's FastAPI backend

Create a `.env` file in `frontend/`:

```env
VITE_API_URL=http://localhost:8000
VITE_USE_MOCK=false
```

Restart Vite after changing environment variables. The backend must implement:

- `POST /ask`
- `GET /health`

Expected `POST /ask` request:

```json
{
  "question": "Explain TCP",
  "mode": "normal",
  "language": "en"
}
```

Expected response:

```json
{
  "answer": "TCP is connection-oriented...",
  "confidence": "grounded",
  "sources": [
    {
      "title": "Computer Networks",
      "chapter": "Transport Layer",
      "page": 42,
      "excerpt": "..."
    }
  ],
  "mode": "offline"
}
```

`GET /health` should return a JSON object containing at least `online` if the frontend status indicator is to reflect the backend's connectivity state. Suggested fields: `status`, `model_available`, `knowledge_base_ready`, `online`.

Configure CORS in FastAPI to allow `http://localhost:5173`.

## Important prototype notes

- Mock mode returns illustrative sample answers and citations; it does not query real textbooks or Ollama.
- The textbook upload control is a placeholder until an upload/indexing API exists.
- The current recent-conversation list is in-memory UI state, not persistent chat storage.
- For a genuinely offline demo, download npm dependencies and the model beforehand, and avoid relying on external fonts. The CSS currently requests Google Fonts and falls back to system fonts if unavailable.
- The UI's offline/online label is a demo status until connected to the real `/health` response.
