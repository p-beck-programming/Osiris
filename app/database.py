from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "osiris.db"


def _db_path() -> Path:
    raw = os.getenv("OSIRIS_DB_PATH")
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(raw)
    return path if path.is_absolute() else ROOT_DIR / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ideas (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL DEFAULT 'local',
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active', 'archived')),
                source TEXT NOT NULL DEFAULT 'text',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                idea_id TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'text',
                created_at TEXT NOT NULL,
                FOREIGN KEY(idea_id) REFERENCES ideas(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_ideas_updated_at
                ON ideas(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notes_idea_created_at
                ON notes(idea_id, created_at ASC);
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '1')"
        )


def derive_title(text: str) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        return "Untitled idea"
    first = compact.split(". ", 1)[0].strip()
    return first[:72] + ("…" if len(first) > 72 else "")


def _serialize_idea(row: sqlite3.Row, latest_note: sqlite3.Row | None = None) -> dict[str, Any]:
    item = dict(row)
    if latest_note:
        item["latest_note"] = latest_note["content"]
        item["latest_note_at"] = latest_note["created_at"]
    return item


def create_idea(initial_note: str, title: str | None = None, source: str = "text") -> dict[str, Any]:
    now = utc_now()
    idea_id = str(uuid4())
    note_id = str(uuid4())
    resolved_title = (title or "").strip() or derive_title(initial_note)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ideas(id, title, status, source, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?, ?)
            """,
            (idea_id, resolved_title, source, now, now),
        )
        conn.execute(
            """
            INSERT INTO notes(id, idea_id, content, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (note_id, idea_id, initial_note.strip(), source, now),
        )

    try:
        from app.semantic.sync import add_note_to_index
        add_note_to_index(note_id)
    except Exception as exc:
        print(f"Semantic indexing failed for note {note_id}: {exc}")

    return get_idea(idea_id)


def list_ideas(search: str = "", status: str = "active", limit: int = 100) -> list[dict[str, Any]]:
    search = search.strip()
    status_clause = "" if status == "all" else "AND i.status = ?"
    params: list[Any] = []

    query = """
        SELECT i.*,
               n.content AS latest_note,
               n.created_at AS latest_note_at,
               (SELECT COUNT(*) FROM notes c WHERE c.idea_id = i.id) AS note_count
        FROM ideas i
        LEFT JOIN notes n ON n.id = (
            SELECT n2.id FROM notes n2
            WHERE n2.idea_id = i.id
            ORDER BY n2.created_at DESC
            LIMIT 1
        )
        WHERE 1 = 1
    """

    if status != "all":
        query += status_clause
        params.append(status)

    if search:
        query += """
            AND (
                i.title LIKE ? COLLATE NOCASE
                OR EXISTS (
                    SELECT 1 FROM notes s
                    WHERE s.idea_id = i.id
                      AND s.content LIKE ? COLLATE NOCASE
                )
            )
        """
        needle = f"%{search}%"
        params.extend([needle, needle])

    query += " ORDER BY i.updated_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))

    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_idea(idea_id: str) -> dict[str, Any]:
    with connect() as conn:
        idea = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        if not idea:
            raise KeyError(idea_id)
        notes = conn.execute(
            "SELECT * FROM notes WHERE idea_id = ? ORDER BY created_at ASC",
            (idea_id,),
        ).fetchall()

    result = dict(idea)
    result["notes"] = [dict(note) for note in notes]
    return result


def update_idea(idea_id: str, title: str | None = None, status: str | None = None) -> dict[str, Any]:
    updates: list[str] = []
    values: list[Any] = []

    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty")
        updates.append("title = ?")
        values.append(cleaned)

    if status is not None:
        if status not in {"active", "archived"}:
            raise ValueError("Invalid status")
        updates.append("status = ?")
        values.append(status)

    if not updates:
        return get_idea(idea_id)

    updates.append("updated_at = ?")
    values.append(utc_now())
    values.append(idea_id)

    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE ideas SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            raise KeyError(idea_id)

    try:
        from app.semantic.index import build_index
        build_index()
    except Exception as exc:
        print(f"Semantic index rebuild failed after updating idea {idea_id}: {exc}")

    return get_idea(idea_id)


def add_note(idea_id: str, content: str, source: str = "text") -> dict[str, Any]:
    content = content.strip()
    if not content:
        raise ValueError("Note cannot be empty")

    now = utc_now()
    note_id = str(uuid4())

    with connect() as conn:
        if not conn.execute("SELECT 1 FROM ideas WHERE id = ?", (idea_id,)).fetchone():
            raise KeyError(idea_id)
        conn.execute(
            """
            INSERT INTO notes(id, idea_id, content, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (note_id, idea_id, content, source, now),
        )
        conn.execute("UPDATE ideas SET updated_at = ? WHERE id = ?", (now, idea_id))

    try:
        from app.semantic.sync import add_note_to_index
        add_note_to_index(note_id)
    except Exception as exc:
        print(f"Semantic indexing failed for note {note_id}: {exc}")

    return get_idea(idea_id)


def dashboard() -> dict[str, Any]:
    with connect() as conn:
        active_count = conn.execute(
            "SELECT COUNT(*) FROM ideas WHERE status = 'active'"
        ).fetchone()[0]
        note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]

    return {
        "active_idea_count": active_count,
        "note_count": note_count,
        "recent_ideas": list_ideas(limit=5),
    }
