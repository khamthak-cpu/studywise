
"""StudyWise chat history API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import chat_history as svc

router = APIRouter(prefix="/history", tags=["chat history"])


def student(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 80:
        raise HTTPException(
            status_code=400,
            detail="student_id must be 1–80 characters",
        )
    return value


class ConversationIn(BaseModel):
    student_id: str = "demo-student"
    title: str = Field(default="New chat", max_length=160)


class MessageIn(BaseModel):
    student_id: str = "demo-student"
    role: str
    content: str = Field(min_length=1, max_length=50000)


@router.get("/conversations")
def list_conversations(student_id: str = "demo-student"):
    return {
        "items": svc.list_conversations(student(student_id))
    }


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationIn):
    return svc.create_conversation(
        student(body.student_id),
        body.title,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    student_id: str = "demo-student",
):
    item = svc.get_conversation(
        student(student_id),
        conversation_id,
    )
    if item is None:
        raise HTTPException(404, "Conversation not found")
    return item


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=201,
)
def add_message(conversation_id: int, body: MessageIn):
    try:
        item = svc.add_message(
            student(body.student_id),
            conversation_id,
            body.role,
            body.content,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if item is None:
        raise HTTPException(404, "Conversation not found")

    return item


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    student_id: str = "demo-student",
):
    deleted = svc.delete_conversation(
        student(student_id),
        conversation_id,
    )
    if not deleted:
        raise HTTPException(404, "Conversation not found")
    return None
