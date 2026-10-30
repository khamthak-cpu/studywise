from unittest.mock import AsyncMock


def test_health_route_reports_degraded_when_models_missing(test_app, monkeypatch):
    app, client = test_app

    class ModelList:
        models = []

    app.state.ollama.list = AsyncMock(return_value=ModelList())
    monkeypatch.setattr("app.routes.health.is_online", AsyncMock(return_value=False))

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ollama"] is True
    assert response.json()["index"]["ready"] is False


def test_ask_returns_expected_response_shape(test_app):
    app, client = test_app
    response = client.post("/ask", json={"question": "What is a variable?", "mode": "offline"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "A test answer."
    assert data["answered_from"] == "model"
    assert data["sources"] == []
    assert data["language"] == "en"
    assert isinstance(data["latency_ms"], int)
    assert len(app.state.llm.generate_calls) == 1


def test_ask_rejects_empty_question(test_app):
    _, client = test_app
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_history_validates_student_id(test_app):
    _, client = test_app
    response = client.get("/history/conversations", params={"student_id": "   "})
    assert response.status_code == 400


def test_upload_route_rejects_blank_student_id(test_app):
    _, client = test_app
    response = client.post(
        "/uploads",
        data={"student_id": "   ", "conversation_id": "1"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_ask_returns_controlled_error_when_llm_fails(test_app):
    app, client = test_app

    async def fail_generation(messages):
        raise RuntimeError("simulated model failure")

    app.state.llm.generate = fail_generation
    response = client.post("/ask", json={"question": "Explain gravity", "mode": "offline"})
    assert response.status_code == 503
    assert "Could not generate an answer" in response.json()["detail"]


def test_short_followup_is_rewritten_with_previous_topic():
    from app.routes.ask import _standalone_query

    history = [
        {"role": "user", "content": "Explain Newton's second law."},
        {"role": "assistant", "content": "It relates net force, mass and acceleration."},
    ]
    rewritten = _standalone_query("Why?", history)
    assert "Newton's second law" in rewritten
    assert "net force" in rewritten


def test_short_followup_without_history_stays_unchanged():
    from app.routes.ask import _standalone_query

    assert _standalone_query("Why?", []) == "Why?"


def test_coding_mode_is_explicit_not_keyword_guessed():
    from app.routes.ask import _is_coding_request
    from app.schemas import AskRequest

    assert not _is_coding_request(AskRequest(question="Explain Python's role in science"))
    assert _is_coding_request(AskRequest(question="write a program", coding_mode=True))
