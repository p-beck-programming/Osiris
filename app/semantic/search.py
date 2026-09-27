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


def load_index():
    index = faiss.read_index(str(INDEX_PATH))

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return index, metadata


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

    return dict(row) if row else None


def semantic_search(query, limit=5):
    index, metadata = load_index()

    query_vector = embed_text(query)
    query_matrix = np.asarray([query_vector], dtype="float32")

    scores, positions = index.search(query_matrix, limit)

    results = []

    for score, position in zip(scores[0], positions[0]):
        if position == -1:
            continue

        metadata_item = metadata[position]
        note = get_note(metadata_item["note_id"])

        if note is None:
            continue

        note["score"] = float(score)
        results.append(note)

    return results
