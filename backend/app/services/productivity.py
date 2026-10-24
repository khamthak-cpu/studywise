"""SQLite persistence and transparent productivity scoring for StudyWise."""
from __future__ import annotations
import os, sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("STUDYWISE_DB_PATH", str(Path(__file__).resolve().parents[3] / "data" / "studywise.sqlite3")))
SCORING_VERSION = "balanced-v1"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS study_tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, title TEXT NOT NULL,
          subject TEXT NOT NULL, planned_minutes INTEGER NOT NULL DEFAULT 25,
          due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed')),
          created_at TEXT NOT NULL, completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_student_day ON study_tasks(student_id, due_date);
        CREATE TABLE IF NOT EXISTS study_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, subject TEXT NOT NULL,
          task_id INTEGER REFERENCES study_tasks(id) ON DELETE SET NULL,
          started_at TEXT NOT NULL, ended_at TEXT NOT NULL, focused_seconds INTEGER NOT NULL,
          interruptions INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_student_start ON study_sessions(student_id, started_at);
        CREATE TABLE IF NOT EXISTS assessments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, subject TEXT NOT NULL,
          total_questions INTEGER NOT NULL, correct_answers INTEGER NOT NULL,
          taken_at TEXT NOT NULL, delayed_recall INTEGER NOT NULL DEFAULT 0 CHECK(delayed_recall IN (0,1))
        );
        CREATE INDEX IF NOT EXISTS idx_assessments_student_time ON assessments(student_id, taken_at);
        CREATE TABLE IF NOT EXISTS daily_reflections (
          student_id TEXT NOT NULL, day TEXT NOT NULL, reflection TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(student_id, day)
        );
        """)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day(value: str | None = None) -> str:
    if value:
        try: return date.fromisoformat(value).isoformat()
        except ValueError as exc: raise ValueError("date must use YYYY-MM-DD") from exc
    return date.today().isoformat()


def create_task(student_id: str, title: str, subject: str, planned_minutes: int, due_date: str) -> dict[str, Any]:
    due = _day(due_date)
    with connect() as db:
        cur = db.execute("INSERT INTO study_tasks(student_id,title,subject,planned_minutes,due_date,created_at) VALUES(?,?,?,?,?,?)",
                          (student_id,title.strip(),subject.strip(),planned_minutes,due,_now().isoformat()))
        return dict(db.execute("SELECT * FROM study_tasks WHERE id=?", (cur.lastrowid,)).fetchone())


def list_tasks(student_id: str, day: str) -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM study_tasks WHERE student_id=? AND due_date=? ORDER BY status, id DESC", (student_id,_day(day))).fetchall()]


def complete_task(student_id: str, task_id: int, completed: bool) -> dict[str, Any] | None:
    with connect() as db:
        cur = db.execute("UPDATE study_tasks SET status=?, completed_at=? WHERE id=? AND student_id=?",
            ("completed" if completed else "pending", _now().isoformat() if completed else None, task_id, student_id))
        if cur.rowcount == 0: return None
        return dict(db.execute("SELECT * FROM study_tasks WHERE id=?", (task_id,)).fetchone())


def create_session(student_id: str, subject: str, started_at: str, ended_at: str, focused_seconds: int, interruptions: int, task_id: int | None, note: str) -> dict[str, Any]:
    with connect() as db:
        if task_id is not None and not db.execute("SELECT 1 FROM study_tasks WHERE id=? AND student_id=?", (task_id,student_id)).fetchone():
            raise ValueError("task not found for this student")
        cur = db.execute("INSERT INTO study_sessions(student_id,subject,task_id,started_at,ended_at,focused_seconds,interruptions,note) VALUES(?,?,?,?,?,?,?,?)",
            (student_id,subject.strip(),task_id,started_at,ended_at,focused_seconds,interruptions,note.strip()))
        return dict(db.execute("SELECT * FROM study_sessions WHERE id=?",(cur.lastrowid,)).fetchone())


def create_assessment(student_id: str, subject: str, total: int, correct: int, taken_at: str, delayed_recall: bool) -> dict[str, Any]:
    with connect() as db:
        cur = db.execute("INSERT INTO assessments(student_id,subject,total_questions,correct_answers,taken_at,delayed_recall) VALUES(?,?,?,?,?,?)",
            (student_id,subject.strip(),total,correct,taken_at,int(delayed_recall)))
        return dict(db.execute("SELECT * FROM assessments WHERE id=?",(cur.lastrowid,)).fetchone())


def save_reflection(student_id: str, day: str, reflection: str) -> dict[str, Any]:
    day = _day(day)
    with connect() as db:
        db.execute("INSERT INTO daily_reflections(student_id,day,reflection) VALUES(?,?,?) ON CONFLICT(student_id,day) DO UPDATE SET reflection=excluded.reflection", (student_id,day,reflection.strip()))
        return dict(db.execute("SELECT * FROM daily_reflections WHERE student_id=? AND day=?",(student_id,day)).fetchone())


def summary(student_id: str, day: str | None = None) -> dict[str, Any]:
    day = _day(day)
    with connect() as db:
        tasks = db.execute("SELECT COUNT(*) total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed FROM study_tasks WHERE student_id=? AND due_date=?",(student_id,day)).fetchone()
        sessions = db.execute("SELECT COALESCE(SUM(focused_seconds),0) seconds, COALESCE(SUM(interruptions),0) interruptions, COUNT(*) count FROM study_sessions WHERE student_id=? AND date(started_at)=?",(student_id,day)).fetchone()
        assessments = db.execute("SELECT COALESCE(SUM(total_questions),0) total, COALESCE(SUM(correct_answers),0) correct, COUNT(*) count FROM assessments WHERE student_id=? AND date(taken_at)=?",(student_id,day)).fetchone()
        reflection = db.execute("SELECT reflection FROM daily_reflections WHERE student_id=? AND day=?",(student_id,day)).fetchone()
    task_total, task_done = tasks["total"], tasks["completed"] or 0
    task_score = round(task_done / task_total * 100) if task_total else None
    # Focus earns credit up to 120 minutes/day; additional time is still displayed, not rewarded.
    focus_minutes = round(sessions["seconds"] / 60, 1)
    focus_score = min(100, round(focus_minutes / 120 * 100)) if sessions["count"] else None
    learning_score = round(assessments["correct"] / assessments["total"] * 100) if assessments["total"] else None
    # Missing categories are excluded and weights re-normalized rather than treated as zero.
    components = [(35,task_score),(25,focus_score),(30,learning_score),(10,100 if (reflection and reflection["reflection"].strip()) else 0 if sessions["count"] or task_total or assessments["count"] or (reflection and reflection["reflection"].strip()) else None)]
    available = [(w,s) for w,s in components if s is not None]
    score = round(sum(w*s for w,s in available) / sum(w for w,_ in available)) if available else None
    with connect() as db:
        week_tasks = db.execute("SELECT COUNT(*) total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed FROM study_tasks WHERE student_id=? AND due_date BETWEEN date(?, '-6 day') AND date(?)",(student_id,day,day)).fetchone()
        week_assess = db.execute("SELECT COALESCE(SUM(total_questions),0) total, COALESCE(SUM(correct_answers),0) correct FROM assessments WHERE student_id=? AND date(taken_at) BETWEEN date(?, '-6 day') AND date(?)",(student_id,day,day)).fetchone()
        week_seconds = db.execute("SELECT COALESCE(SUM(focused_seconds),0) FROM study_sessions WHERE student_id=? AND date(started_at) BETWEEN date(?, '-6 day') AND date(?)",(student_id,day,day)).fetchone()[0]
        days = db.execute("SELECT date(?, '-' || n || ' day') day FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6) ORDER BY day",(day,)).fetchall()
        daily_seconds = {r["day"]:r["seconds"] for r in db.execute("SELECT date(started_at) day, SUM(focused_seconds) seconds FROM study_sessions WHERE student_id=? AND date(started_at) BETWEEN date(?, '-6 day') AND date(?) GROUP BY date(started_at)",(student_id,day,day)).fetchall()}
    return {"student_id":student_id,"date":day,"score":score,"scoring_version":SCORING_VERSION,
        "components":{"task_completion":{"score":task_score,"weight":35,"completed":int(task_done),"total":task_total},"focus":{"score":focus_score,"weight":25,"focused_minutes":focus_minutes,"target_minutes":120},"learning":{"score":learning_score,"weight":30,"correct":int(assessments['correct']),"questions":int(assessments['total'])},"reflection":{"score":100 if reflection and reflection['reflection'].strip() else (0 if task_total or sessions['count'] or assessments['count'] or (reflection and reflection['reflection'].strip()) else None),"weight":10,"completed":bool(reflection and reflection['reflection'].strip())}},
        "tasks":{"completed":int(task_done),"total":task_total},"focused_minutes":focus_minutes,"interruptions":int(sessions['interruptions']),"session_count":int(sessions['count']),"learning":{"correct":int(assessments['correct']),"questions":int(assessments['total']),"accuracy":learning_score},"reflection":reflection['reflection'] if reflection else "",
        "week":{"focused_minutes":round(week_seconds/60,1),"tasks_completed":int(week_tasks['completed'] or 0),"tasks_total":int(week_tasks['total']),"quiz_accuracy":round(week_assess['correct']/week_assess['total']*100) if week_assess['total'] else None,"daily_focus":[{"date":r['day'],"minutes":round(daily_seconds.get(r['day'],0)/60,1)} for r in days]}}
