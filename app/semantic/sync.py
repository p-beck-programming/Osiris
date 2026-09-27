import json
import sqlite3
from pathlib import Path

import faiss
import numpy as np

from app.semantic.embedder import embed_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "data" / "osiris.db"
INDEX_PATH = PROJECT_ROOT / "data" / "semantic.index"
METADATA_PATH = PROJECT_ROOT / "data" / "semantic_metadata.json"


def get_note(note_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT
            notes.id AS note_id,
            notes.idea_id,
            notes.content,
            notes.created_at,
            ideas.title AS idea_title
        FROM notes
        JOIN ideas ON ideas.id = notes.idea_id
        WHERE notes.id = ?
        """,
        (note_id,),
    ).fetchone()

    conn.close()

    return row


def add_note_to_index(note_id):
    row = get_note(note_id)

    if row is None:
        raise ValueError(f"Note not found: {note_id}")

    text = (
        f"Idea: {row['idea_title']}\n\n"
        f"Note:\n{row['content']}"
    )

    vector = embed_text(text)
    vector = np.asarray([vector], dtype="float32")

    index = faiss.read_index(str(INDEX_PATH))

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    index.add(vector)

    metadata.append(
        {
            "note_id": row["note_id"],
            "idea_id": row["idea_id"],
            "idea_title": row["idea_title"],
            "created_at": row["created_at"],
        }
    )

    faiss.write_index(index, str(INDEX_PATH))

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Indexed new note: {note_id}")
