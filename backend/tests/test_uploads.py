import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.services import attachments


@pytest.fixture

def upload_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"

    def connect():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    with connect() as db:
        db.executescript("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY, student_id TEXT NOT NULL
        );
        INSERT INTO conversations (id, student_id) VALUES (1, 'student-a');
        CREATE TABLE attachments (
            id TEXT PRIMARY KEY, student_id TEXT NOT NULL,
            conversation_id INTEGER NOT NULL, filename TEXT NOT NULL,
            extension TEXT NOT NULL, content_type TEXT NOT NULL,
            storage_path TEXT NOT NULL, extracted_text TEXT NOT NULL DEFAULT '',
            sha256 TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
    monkeypatch.setattr(attachments, "connect", connect)
    monkeypatch.setattr(attachments, "init_attachments_db", lambda: None)
    monkeypatch.setattr(attachments, "UPLOAD_DIR", tmp_path / "uploads")
    return db_path


def make_upload(name: str, content: bytes) -> UploadFile:
    from io import BytesIO
    return UploadFile(
        filename=name,
        file=BytesIO(content),
        headers=Headers({"content-type": "application/octet-stream"}),
    )


@pytest.mark.asyncio
async def test_txt_upload_is_saved_and_text_extracted(upload_db):
    result = await attachments.save_upload(
        make_upload("revision.txt", b"Cell structure and function"),
        "student-a", 1,
    )
    assert result["filename"] == "revision.txt"
    assert result["kind"] == "document"
    items = attachments.get_conversation_attachments("student-a", 1)
    assert len(items) == 1
    assert items[0]["extracted_text"] == "Cell structure and function"
    assert Path(items[0]["storage_path"]).exists()


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension(upload_db):
    with pytest.raises(HTTPException) as exc:
        await attachments.save_upload(make_upload("payload.exe", b"MZ"), "student-a", 1)
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_content_that_does_not_match_extension(upload_db):
    with pytest.raises(HTTPException) as exc:
        await attachments.save_upload(make_upload("notes.pdf", b"not a pdf"), "student-a", 1)
    assert exc.value.status_code == 415
    assert list((Path(attachments.UPLOAD_DIR)).glob("*")) == []


@pytest.mark.asyncio
async def test_upload_cannot_attach_to_another_students_conversation(upload_db):
    with pytest.raises(HTTPException) as exc:
        await attachments.save_upload(make_upload("notes.txt", b"hello"), "student-b", 1)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(upload_db):
    with pytest.raises(HTTPException) as exc:
        await attachments.save_upload(make_upload("empty.txt", b""), "student-a", 1)
    assert exc.value.status_code == 400
