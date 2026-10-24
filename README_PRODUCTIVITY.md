# StudyWise Productivity Prototype

This change adds a student productivity dashboard to the existing React + FastAPI StudyWise prototype.

## Features
- SQLite persistence for study tasks, focus sessions, quiz results, and daily reflections.
- Daily task planning and completion.
- Manual focus-session logging with subject, optional task association, duration, and interruption count.
- Quiz accuracy tracking and an optional delayed-recall flag.
- Daily productivity score and seven-day focus/task/quiz summaries.
- Responsive dashboard UI available from the sidebar's **Productivity** item.

## Run locally

Backend (from `studywise/backend`):

```bash
python -m venv .venv
# Activate the environment, then:
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (from `studywise/frontend`):

```bash
npm ci
npm run dev
```

Set `VITE_API_URL` in the frontend environment if the API is not at `http://localhost:8000`. The API creates `data/studywise.sqlite3` by default. Set `STUDYWISE_DB_PATH` to use a different path (useful for tests and local deployments).

## API
- `GET /productivity/summary?student_id=demo-student&date=YYYY-MM-DD`
- `GET /productivity/tasks?student_id=demo-student&date=YYYY-MM-DD`
- `POST /productivity/tasks`
- `PATCH /productivity/tasks/{task_id}`
- `POST /productivity/sessions`
- `POST /productivity/assessments`
- `PUT /productivity/reflection`

The request/response schemas are documented by FastAPI at `/docs` when the server is running.

## Prototype score
Scoring version `balanced-v1` uses task completion 35%, focus time 25%, quiz accuracy 30%, and reflection 10%. Focus time is capped at 120 minutes for score credit; actual recorded minutes are still displayed. Components without evidence are excluded and remaining weights normalized, so an empty day does not automatically receive a zero. Once activity exists, a missing quiz or reflection is not treated as successful evidence. This is a transparent prototype metric, **not a validated measure of ability or a grade predictor**. The weights and thresholds need user research and validation.

## Important limitations / deployment blockers
- `demo-student` is a prototype identity, not authentication. Do not expose this API publicly or use it with real student records until proper authentication, authorization, rate limiting, and student-level access control are implemented.
- SQLite is appropriate for local prototyping or a small single-instance deployment; assess PostgreSQL before multi-instance or higher-concurrency use.
- Focus sessions are manually logged after completion; no live timer or interruption detection is implemented yet.
- Quiz results are self-reported; there is no quiz authoring, answer validation, or verified delayed-recall scheduler in this feature.
- Session dates are derived from stored ISO timestamps using SQLite date functions (UTC behavior). Local-timezone day boundaries should be made explicit before launch.
- No frontend production build could be confirmed in the current environment if npm dependencies cannot be installed. Run `npm ci && npm run build` in a network-enabled environment.
