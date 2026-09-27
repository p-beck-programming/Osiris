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


def load_notes():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            notes.id AS note_id,
            notes.idea_id,
            notes.content,
            notes.created_at,
            ideas.title AS idea_title,
            ideas.status AS idea_status
        FROM notes
        JOIN ideas ON ideas.id = notes.idea_id
        WHERE ideas.status = 'active'
        ORDER BY notes.created_at ASC
        """
    ).fetchall()

    conn.close()

    return rows


def build_index():
    rows = load_notes()

    if not rows:
        print("No notes found. Nothing to index.")
        return

    vectors = []
    metadata = []

    for row in rows:
        text = (
            f"Idea: {row['idea_title']}\n\n"
            f"Note:\n{row['content']}"
        )

        vector = embed_text(text)

        vectors.append(vector)

        metadata.append(
            {
                "note_id": row["note_id"],
                "idea_id": row["idea_id"],
                "idea_title": row["idea_title"],
                "created_at": row["created_at"],
            }
        )

    matrix = np.asarray(vectors, dtype="float32")

    dimension = matrix.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(matrix)

    faiss.write_index(index, str(INDEX_PATH))

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Indexed {len(metadata)} notes.")
    print(f"FAISS index: {INDEX_PATH}")
    print(f"Metadata: {METADATA_PATH}")


if __name__ == "__main__":
    build_index()
