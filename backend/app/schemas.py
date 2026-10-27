
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Subject = Literal["science", "math", "commerce", "social_science"]
Mode = Literal["auto", "offline", "online"]
AnswerOrigin = Literal["model", "notes", "web", "mixed", "fallback"]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: int | None = Field(default=None, gt=0)
    attachment_ids: list[str] = Field(default_factory=list, max_length=5)
    student_id: str = Field(default="demo-student", min_length=1, max_length=80)
    class_level: int | None = Field(default=None, ge=8, le=12)
    subject: Subject | None = None
    language: Literal["auto", "en", "hi"] = "auto"
    simplify: bool = False
    mode: Mode = "auto"

    @model_validator(mode="after")
    def _check_combo(self):
        if (
            self.subject == "commerce"
            and self.class_level is not None
            and self.class_level < 11
        ):
            raise ValueError("Commerce is available for Class 11-12 only")
        return self


class Source(BaseModel):
    id: int = 0
    kind: Literal["notes", "web"] = "notes"
    title: str
    section: str | None = None
    page: int | None = None
    url: str | None = None
    score: float | None = None
    snippet: str
    text: str = Field(exclude=True)


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: float
    answered_from: AnswerOrigin
    language: Literal["en", "hi"]
    online: bool
    latency_ms: int
