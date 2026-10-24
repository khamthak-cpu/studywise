
"""SQLite persistence and transparent productivity scoring for StudyWise."""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter

router = APIRouter(
    prefix="/productivity",
    tags=["productivity"],
)

DB_PATH = Path(
    os.getenv(
        "STUDYWISE_DB_PATH",
        str(Path(__file__).resolve().parents[3] / "data" / "studywise.sqlite3"),
    )
)

SCORING_VERSION = "balanced-v1"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")

    return db


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS study_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                planned_minutes INTEGER NOT NULL DEFAULT 25,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'completed')),
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_student_day
                ON study_tasks(student_id, due_date);

            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                task_id INTEGER REFERENCES study_tasks(id)
                    ON DELETE SET NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                focused_seconds INTEGER NOT NULL,
                interruptions INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_student_start
                ON study_sessions(student_id, started_at);

            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                correct_answers INTEGER NOT NULL,
                taken_at TEXT NOT NULL,
                delayed_recall INTEGER NOT NULL DEFAULT 0
                    CHECK(delayed_recall IN (0, 1))
            );

            CREATE INDEX IF NOT EXISTS idx_assessments_student_time
                ON assessments(student_id, taken_at);

            CREATE TABLE IF NOT EXISTS daily_reflections (
                student_id TEXT NOT NULL,
                day TEXT NOT NULL,
                reflection TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(student_id, day)
            );
            """
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day(value: str | None = None) -> str:
    if value is None:
        return _now().date().isoformat()

    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc

    # Reject noncanonical values such as malformed ISO representations.
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")

    return parsed.isoformat()


def _aware_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a valid ISO datetime") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")

    return parsed.astimezone(timezone.utc)


def create_task(
    student_id: str,
    title: str,
    subject: str,
    planned_minutes: int,
    due_date: str,
) -> dict[str, Any]:
    title = title.strip()
    subject = subject.strip()
    due = _day(due_date)

    if not title:
        raise ValueError("title cannot be empty")
    if not subject:
        raise ValueError("subject cannot be empty")
    if not 5 <= planned_minutes <= 480:
        raise ValueError("planned_minutes must be between 5 and 480")

    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO study_tasks (
                student_id, title, subject, planned_minutes,
                due_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                title,
                subject,
                planned_minutes,
                due,
                _now().isoformat(),
            ),
        )

        row = db.execute(
            "SELECT * FROM study_tasks WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()

        return dict(row)


def list_tasks(student_id: str, day: str | None = None) -> list[dict[str, Any]]:
    selected_day = _day(day)

    with connect() as db:
        rows = db.execute(
            """
            SELECT *
            FROM study_tasks
            WHERE student_id = ? AND due_date = ?
            ORDER BY status, id DESC
            """,
            (student_id, selected_day),
        ).fetchall()

        return [dict(row) for row in rows]


def complete_task(
    student_id: str,
    task_id: int,
    completed: bool,
) -> dict[str, Any] | None:
    with connect() as db:
        cur = db.execute(
            """
            UPDATE study_tasks
            SET status = ?, completed_at = ?
            WHERE id = ? AND student_id = ?
            """,
            (
                "completed" if completed else "pending",
                _now().isoformat() if completed else None,
                task_id,
                student_id,
            ),
        )

        if cur.rowcount == 0:
            return None

        row = db.execute(
            "SELECT * FROM study_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        return dict(row) if row else None


def create_session(
    student_id: str,
    subject: str,
    started_at: str,
    ended_at: str,
    focused_seconds: int,
    interruptions: int,
    task_id: int | None,
    note: str,
) -> dict[str, Any]:
    subject = subject.strip()
    start = _aware_datetime(started_at, "started_at")
    end = _aware_datetime(ended_at, "ended_at")

    if not subject:
        raise ValueError("subject cannot be empty")
    if end <= start:
        raise ValueError("ended_at must be after started_at")
    if not 1 <= focused_seconds <= 86400:
        raise ValueError("focused_seconds must be between 1 and 86400")

    duration = (end - start).total_seconds()
    if focused_seconds > duration:
        raise ValueError("focused_seconds cannot exceed session duration")
    if not 0 <= interruptions <= 1000:
        raise ValueError("interruptions must be between 0 and 1000")

    with connect() as db:
        if task_id is not None:
            task = db.execute(
                """
                SELECT 1 FROM study_tasks
                WHERE id = ? AND student_id = ?
                """,
                (task_id, student_id),
            ).fetchone()

            if not task:
                raise ValueError("task not found for this student")

        cur = db.execute(
            """
            INSERT INTO study_sessions (
                student_id, subject, task_id, started_at, ended_at,
                focused_seconds, interruptions, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                subject,
                task_id,
                start.isoformat(),
                end.isoformat(),
                focused_seconds,
                interruptions,
                note.strip(),
            ),
        )

        row = db.execute(
            "SELECT * FROM study_sessions WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()

        return dict(row)


def create_assessment(
    student_id: str,
    subject: str,
    total: int,
    correct: int,
    taken_at: str,
    delayed_recall: bool,
) -> dict[str, Any]:
    subject = subject.strip()
    timestamp = _aware_datetime(taken_at, "taken_at")

    if not subject:
        raise ValueError("subject cannot be empty")
    if not 1 <= total <= 500:
        raise ValueError("total_questions must be between 1 and 500")
    if not 0 <= correct <= total:
        raise ValueError("correct_answers must be between 0 and total_questions")

    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO assessments (
                student_id, subject, total_questions,
                correct_answers, taken_at, delayed_recall
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                subject,
                total,
                correct,
                timestamp.isoformat(),
                int(delayed_recall),
            ),
        )

        row = db.execute(
            "SELECT * FROM assessments WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()

        return dict(row)


def save_reflection(
    student_id: str,
    day: str,
    reflection: str,
) -> dict[str, Any]:
    selected_day = _day(day)

    with connect() as db:
        db.execute(
            """
            INSERT INTO daily_reflections (student_id, day, reflection)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, day)
            DO UPDATE SET reflection = excluded.reflection
            """,
            (student_id, selected_day, reflection.strip()),
        )

        row = db.execute(
            """
            SELECT * FROM daily_reflections
            WHERE student_id = ? AND day = ?
            """,
            (student_id, selected_day),
        ).fetchone()

        return dict(row)


def summary(
    student_id: str,
    day: str | None = None,
) -> dict[str, Any]:
    selected_day = _day(day)

    # This implementation groups activity by UTC calendar day.
    # Local-time reporting requires a configured timezone per student.
    with connect() as db:
        tasks = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                    AS completed
            FROM study_tasks
            WHERE student_id = ? AND due_date = ?
            """,
            (student_id, selected_day),
        ).fetchone()

        sessions = db.execute(
            """
            SELECT
                COALESCE(SUM(focused_seconds), 0) AS seconds,
                COALESCE(SUM(interruptions), 0) AS interruptions,
                COUNT(*) AS count
            FROM study_sessions
            WHERE student_id = ? AND date(started_at) = ?
            """,
            (student_id, selected_day),
        ).fetchone()

        assessments = db.execute(
            """
            SELECT
                COALESCE(SUM(total_questions), 0) AS total,
                COALESCE(SUM(correct_answers), 0) AS correct,
                COUNT(*) AS count
            FROM assessments
            WHERE student_id = ? AND date(taken_at) = ?
            """,
            (student_id, selected_day),
        ).fetchone()

        reflection_row = db.execute(
            """
            SELECT reflection FROM daily_reflections
            WHERE student_id = ? AND day = ?
            """,
            (student_id, selected_day),
        ).fetchone()

        week_start = (
            date.fromisoformat(selected_day) - timedelta(days=6)
        ).isoformat()

        week_tasks = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                    AS completed
            FROM study_tasks
            WHERE student_id = ? AND due_date BETWEEN ? AND ?
            """,
            (student_id, week_start, selected_day),
        ).fetchone()

        week_assessments = db.execute(
            """
            SELECT
                COALESCE(SUM(total_questions), 0) AS total,
                COALESCE(SUM(correct_answers), 0) AS correct
            FROM assessments
            WHERE student_id = ?
              AND date(taken_at) BETWEEN ? AND ?
            """,
            (student_id, week_start, selected_day),
        ).fetchone()

        week_seconds = db.execute(
            """
            SELECT COALESCE(SUM(focused_seconds), 0)
            FROM study_sessions
            WHERE student_id = ?
              AND date(started_at) BETWEEN ? AND ?
            """,
            (student_id, week_start, selected_day),
        ).fetchone()[0]

        daily_rows = db.execute(
            """
            SELECT date(started_at) AS day, SUM(focused_seconds) AS seconds
            FROM study_sessions
            WHERE student_id = ?
              AND date(started_at) BETWEEN ? AND ?
            GROUP BY date(started_at)
            """,
            (student_id, week_start, selected_day),
        ).fetchall()

    task_total = int(tasks["total"] or 0)
    task_done = int(tasks["completed"] or 0)
    assessment_total = int(assessments["total"] or 0)
    assessment_correct = int(assessments["correct"] or 0)
    session_count = int(sessions["count"] or 0)

    task_score = (
        round(task_done / task_total * 100)
        if task_total
        else None
    )

    focus_minutes = round(int(sessions["seconds"]) / 60, 1)
    focus_score = (
        min(100, round(focus_minutes / 120 * 100))
        if session_count
        else None
    )

    learning_score = (
        round(assessment_correct / assessment_total * 100)
        if assessment_total
        else None
    )

    reflection_text = (
        reflection_row["reflection"] if reflection_row else ""
    )
    reflection_completed = bool(reflection_text.strip())

    has_activity = bool(
        task_total
        or session_count
        or assessments["count"]
        or reflection_row
    )

    reflection_score = (
        100
        if reflection_completed
        else 0 if has_activity else None
    )

    components = [
        (35, task_score),
        (25, focus_score),
        (30, learning_score),
        (10, reflection_score),
    ]

    available = [
        (weight, score)
        for weight, score in components
        if score is not None
    ]

    overall_score = (
        round(
            sum(weight * score for weight, score in available)
            / sum(weight for weight, _ in available)
        )
        if available
        else None
    )

    daily_seconds = {
        row["day"]: int(row["seconds"] or 0)
        for row in daily_rows
    }

    daily_focus = []
    for offset in range(7):
        current_day = (
            date.fromisoformat(selected_day) - timedelta(days=6 - offset)
        ).isoformat()

        daily_focus.append(
            {
                "date": current_day,
                "minutes": round(
                    daily_seconds.get(current_day, 0) / 60,
                    1,
                ),
            }
        )

    week_assessment_total = int(week_assessments["total"] or 0)
    week_assessment_correct = int(week_assessments["correct"] or 0)

    return {
        "student_id": student_id,
        "date": selected_day,
        "score": overall_score,
        "scoring_version": SCORING_VERSION,
        "components": {
            "task_completion": {
                "score": task_score,
                "weight": 35,
                "completed": task_done,
                "total": task_total,
            },
            "focus": {
                "score": focus_score,
                "weight": 25,
                "focused_minutes": focus_minutes,
                "target_minutes": 120,
            },
            "learning": {
                "score": learning_score,
                "weight": 30,
                "correct": assessment_correct,
                "questions": assessment_total,
            },
            "reflection": {
                "score": reflection_score,
                "weight": 10,
                "completed": reflection_completed,
            },
        },
        "tasks": {
            "completed": task_done,
            "total": task_total,
        },
        "focused_minutes": focus_minutes,
        "interruptions": int(sessions["interruptions"] or 0),
        "session_count": session_count,
        "learning": {
            "correct": assessment_correct,
            "questions": assessment_total,
            "accuracy": learning_score,
        },
        "reflection": reflection_text,
        "week": {
            "focused_minutes": round(int(week_seconds) / 60, 1),
            "tasks_completed": int(week_tasks["completed"] or 0),
            "tasks_total": int(week_tasks["total"] or 0),
            "quiz_accuracy": (
                round(
                    week_assessment_correct
                    / week_assessment_total
                    * 100
                )
                if week_assessment_total
                else None
            ),
            "daily_focus": daily_focus,
        },
    }
