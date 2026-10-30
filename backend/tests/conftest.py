"""Shared fixtures for API and service tests; no real Ollama or network calls."""
from types import SimpleNamespace
import sys
import types

# Keep unit tests runnable without installing or starting Ollama.
if "ollama" not in sys.modules:
    ollama_stub = types.ModuleType("ollama")
    class _ResponseError(Exception):
        pass
    class _AsyncClient:
        pass
    ollama_stub.ResponseError = _ResponseError
    ollama_stub.AsyncClient = _AsyncClient
    sys.modules["ollama"] = ollama_stub

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import ask, health, history, uploads


class FakeLLM:
    def __init__(self, answer="A test answer."):
        self.answer = answer
        self.generate_calls = []

    def build_direct_messages(self, **kwargs):
        return [{"role": "system", "content": "test"}, {"role": "user", "content": kwargs["question"]}]

    def build_messages(self, **kwargs):
        return [{"role": "system", "content": "grounded test"}, {"role": "user", "content": kwargs["question"]}]

    async def generate(self, messages):
        self.generate_calls.append(messages)
        return self.answer

    async def describe_image(self, path):
        return "A test image description."


class FakeRetriever:
    ready = False

    async def search(self, *args, **kwargs):
        return []

    def count(self):
        return 0


@pytest.fixture

def test_app(monkeypatch):
    app = FastAPI()
    app.include_router(ask.router)
    app.include_router(health.router)
    app.include_router(history.router)
    app.include_router(uploads.router)
    app.state.settings = SimpleNamespace(
        web_search_enabled=False,
        min_score=0.45,
        llm_timeout_s=1,
        ollama_host="http://127.0.0.1:11434",
        llm_model="test-model",
        embed_model="test-embed",
        chroma_path="/tmp/no-index-for-tests",
        collection="test",
    )
    app.state.llm = FakeLLM()
    app.state.retriever = FakeRetriever()
    app.state.ollama = SimpleNamespace()

    # Isolate persistence from the user's real local database.
    from app.services import chat_history
    monkeypatch.setattr(chat_history, "get_recent_messages", lambda **kwargs: [])
    monkeypatch.setattr(chat_history, "add_message", lambda **kwargs: {"id": 1})
    monkeypatch.setattr(chat_history, "create_conversation", lambda student_id, title: {"id": 1, "student_id": student_id, "title": title})
    monkeypatch.setattr(chat_history, "list_conversations", lambda student_id: [])
    monkeypatch.setattr(chat_history, "get_conversation", lambda student_id, conversation_id: None)
    monkeypatch.setattr(chat_history, "delete_conversation", lambda student_id, conversation_id: False)
    monkeypatch.setattr(ask, "is_online", _offline)
    monkeypatch.setattr(ask, "get_selected_attachments", lambda *args: [])

    with TestClient(app) as client:
        yield app, client


async def _offline():
    return False
