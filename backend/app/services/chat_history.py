
"""SQLite persistence for StudyWise conversations and messages."""

from datetime import datetime, timezone
from typing import Any

from app.services.productivity import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_history_db() -> None:
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'New chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_owner
                ON conversations(student_id, updated_at);

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id)
                    REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
                ON chat_messages(conversation_id, id);
        """)


def create_conversation(
    student_id: str,
    title: str = "New chat",
) -> dict[str, Any]:
    now = _now()
    title = title.strip()[:160] or "New chat"

    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO conversations
                (student_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, title, now, now),
        )
        row = db.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()

        return dict(row)


def list_conversations(student_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT
                c.id, c.title, c.created_at, c.updated_at,
                COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN chat_messages m ON m.conversation_id = c.id
            WHERE c.student_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC, c.id DESC
            """,
            (student_id,),
        ).fetchall()

        return [dict(row) for row in rows]


def get_conversation(
    student_id: str,
    conversation_id: int,
) -> dict[str, Any] | None:
    with connect() as db:
        conversation = db.execute(
            """
            SELECT id, student_id, title, created_at, updated_at
            FROM conversations
            WHERE id = ? AND student_id = ?
            """,
            (conversation_id, student_id),
        ).fetchone()

        if conversation is None:
            return None

        messages = db.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()

        result = dict(conversation)
        result["messages"] = [dict(row) for row in messages]
        return result


def add_message(
    student_id: str,
    conversation_id: int,
    role: str,
    content: str,
) -> dict[str, Any] | None:
    if role not in {"user", "assistant"}:
        raise ValueError("role must be user or assistant")

    content = content.strip()
    if not content:
        raise ValueError("message content cannot be empty")

    now = _now()

    with connect() as db:
        conversation = db.execute(
            """
            SELECT id, title
            FROM conversations
            WHERE id = ? AND student_id = ?
            """,
            (conversation_id, student_id),
        ).fetchone()

        if conversation is None:
            return None

        db.execute(
            """
            INSERT INTO chat_messages
                (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, now),
        )

        # Use the first user question as the conversation title.
        if role == "user" and conversation["title"] == "New chat":
            title = content[:60]
            if len(content) > 60:
                title = title[:57] + "..."

            db.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND student_id = ?
                """,
                (title, now, conversation_id, student_id),
            )
        else:
            db.execute(
                """
                UPDATE conversations SET updated_at = ?
                WHERE id = ? AND student_id = ?
                """,
                (now, conversation_id, student_id),
            )

        row = db.execute(
            """
            SELECT id, conversation_id, role, content, created_at
            FROM chat_messages
            WHERE id = last_insert_rowid()
            """
        ).fetchone()

        return dict(row)


def delete_conversation(
    student_id: str,
    conversation_id: int,
) -> bool:
    with connect() as db:
        cur = db.execute(
            """
            DELETE FROM conversations
            WHERE id = ? AND student_id = ?
            """,
            (conversation_id, student_id),
        )
        return cur.rowcount > 0

def get_recent_messages(
    student_id: str,
    conversation_id: int,
    limit: int = 16,
) -> list[dict[str, str]]:
    """Return recent messages in chronological order."""
    limit = max(1, min(limit, 40))

    with connect() as db:
        conversation = db.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = ? AND student_id = ?
            """,
            (conversation_id, student_id),
        ).fetchone()

        if conversation is None:
            raise ValueError("Conversation not found")

        rows = db.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

        return [
            {
                "role": row["role"],
                "content": row["content"],
            }
            for row in reversed(rows)
        ]
