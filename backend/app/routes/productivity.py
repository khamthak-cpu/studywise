from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from app.services import productivity as svc

router = APIRouter(prefix="/productivity", tags=["productivity"])
# Prototype identity only. Replace with authenticated user identity before deployment.
def student(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 80: raise HTTPException(400, "student_id must be 1–80 characters")
    return value

class TaskIn(BaseModel):
    student_id: str = "demo-student"
    title: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=80)
    planned_minutes: int = Field(default=25, ge=5, le=480)
    due_date: str | None = None

class TaskStatus(BaseModel):
    student_id: str = "demo-student"
    completed: bool = True

class SessionIn(BaseModel):
    student_id: str = "demo-student"
    subject: str = Field(min_length=1, max_length=80)
    started_at: datetime
    ended_at: datetime
    focused_seconds: int = Field(ge=1, le=86400)
    interruptions: int = Field(default=0, ge=0, le=1000)
    task_id: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=500)
    @field_validator("started_at", "ended_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None: raise ValueError("timestamp must include timezone")
        return value

class AssessmentIn(BaseModel):
    student_id: str = "demo-student"
    subject: str = Field(min_length=1, max_length=80)
    total_questions: int = Field(ge=1, le=500)
    correct_answers: int = Field(ge=0, le=500)
    taken_at: datetime | None = None
    delayed_recall: bool = False
    @field_validator("correct_answers")
    @classmethod
    def valid_correct(cls, value, info):
        total = info.data.get("total_questions")
        if total is not None and value > total: raise ValueError("correct_answers cannot exceed total_questions")
        return value

class ReflectionIn(BaseModel):
    student_id: str = "demo-student"
    date: str | None = None
    reflection: str = Field(default="", max_length=1000)

@router.get("/summary")
def get_summary(student_id: str = "demo-student", day: str | None = Query(default=None, alias="date")):
    try: return svc.summary(student(student_id), day)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@router.get("/tasks")
def get_tasks(student_id: str = "demo-student", day: str | None = Query(default=None, alias="date")):
    try: return {"items":svc.list_tasks(student(student_id),day)}
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@router.post("/tasks", status_code=201)
def post_task(body: TaskIn):
    try: return svc.create_task(student(body.student_id),body.title,body.subject,body.planned_minutes,body.due_date or datetime.now().date().isoformat())
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskStatus):
    item = svc.complete_task(student(body.student_id),task_id,body.completed)
    if item is None: raise HTTPException(404,"Task not found")
    return item

@router.post("/sessions", status_code=201)
def post_session(body: SessionIn):
    if body.ended_at <= body.started_at: raise HTTPException(422,"ended_at must be after started_at")
    if body.focused_seconds > (body.ended_at-body.started_at).total_seconds(): raise HTTPException(422,"focused_seconds cannot exceed session duration")
    try: return svc.create_session(student(body.student_id),body.subject,body.started_at.isoformat(),body.ended_at.isoformat(),body.focused_seconds,body.interruptions,body.task_id,body.note)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@router.post("/assessments", status_code=201)
def post_assessment(body: AssessmentIn):
    at = body.taken_at or datetime.now(timezone.utc)
    if at.tzinfo is None: raise HTTPException(422,"taken_at must include timezone")
    return svc.create_assessment(student(body.student_id),body.subject,body.total_questions,body.correct_answers,at.isoformat(),body.delayed_recall)

@router.put("/reflection")
def put_reflection(body: ReflectionIn):
    try: return svc.save_reflection(student(body.student_id),body.date or datetime.now().date().isoformat(),body.reflection)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
