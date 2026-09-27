from __future__ import annotations

from typing import Any, Collection

import numpy as np

from app.database import connect
from app.semantic.embedder import embed_text


MIN_GROUPING_SCORE = 0.44
MIN_GROUPING_MARGIN = 0.06


def normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def load_active_ideas() -> list[dict[str, Any]]:
    """Load active ideas and their notes from SQLite."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                i.id AS idea_id,
                i.title AS idea_title,
                i.created_at,
                i.updated_at,
                n.id AS note_id,
                n.content AS note_content,
                n.created_at AS note_created_at
            FROM ideas i
            LEFT JOIN notes n ON n.idea_id = i.id
            WHERE i.status = 'active'
            ORDER BY i.updated_at DESC, n.created_at ASC
            """
        ).fetchall()

    ideas_by_id: dict[str, dict[str, Any]] = {}

    for row in rows:
        idea_id = row["idea_id"]
        idea = ideas_by_id.setdefault(
            idea_id,
            {
                "idea_id": idea_id,
                "title": row["idea_title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "notes": [],
            },
        )

        if row["note_id"] is not None:
            idea["notes"].append(
                {
                    "note_id": row["note_id"],
                    "content": row["note_content"],
                    "created_at": row["note_created_at"],
                }
            )

    return list(ideas_by_id.values())


def build_idea_vector(idea: dict[str, Any]) -> np.ndarray | None:
    """Build a normalized centroid from an idea's contextualized notes."""
    notes = idea.get("notes", [])
    if not notes:
        return None

    vectors = []
    for note in notes:
        embedding_text = (
            f"Idea: {idea['title']}\n\n"
            f"Note:\n{note['content']}"
        )
        vectors.append(embed_text(embedding_text))

    matrix = np.asarray(vectors, dtype="float32")
    centroid = matrix.mean(axis=0)
    norm = float(np.linalg.norm(centroid))

    if norm == 0:
        return None

    return (centroid / norm).astype("float32")


def find_best_ideas(
    note_text: str,
    limit: int = 5,
    exclude_idea_ids: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank active ideas for an incoming note without modifying data."""
    cleaned = note_text.strip()
    if not cleaned:
        raise ValueError("Note text cannot be empty")
    if limit < 1:
        raise ValueError("Limit must be at least 1")

    excluded = set(exclude_idea_ids or ())
    query_vector = np.asarray(embed_text(cleaned), dtype="float32")
    query_norm = float(np.linalg.norm(query_vector))

    if query_norm == 0:
        return []

    query_vector /= query_norm
    candidates = []

    for idea in load_active_ideas():
        if idea["idea_id"] in excluded:
            continue

        idea_vector = build_idea_vector(idea)
        if idea_vector is None:
            continue

        candidates.append(
            {
                "idea_id": idea["idea_id"],
                "title": idea["title"],
                "score": float(np.dot(query_vector, idea_vector)),
                "note_count": len(idea["notes"]),
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:limit]


def decide_grouping(
    note_text: str,
    min_score: float = MIN_GROUPING_SCORE,
    min_margin: float = MIN_GROUPING_MARGIN,
    exclude_idea_ids: Collection[str] | None = None,
) -> dict[str, Any]:
    """Recommend an existing idea or a new idea without writing data."""
    candidates = find_best_ideas(
        note_text,
        limit=10,
        exclude_idea_ids=exclude_idea_ids,
    )

    if not candidates:
        return {
            "action": "create_new_idea",
            "idea_id": None,
            "title": None,
            "best_candidate": None,
            "second_candidate": None,
            "margin": None,
            "reason": "No active ideas are available.",
        }

    best = candidates[0]
    best_title_key = normalize_title(best["title"])
    second = next(
        (
            candidate
            for candidate in candidates[1:]
            if normalize_title(candidate["title"]) != best_title_key
        ),
        None,
    )

    second_score = second["score"] if second else 0.0
    margin = best["score"] - second_score
    confident = best["score"] >= min_score and margin >= min_margin

    return {
        "action": "add_to_existing" if confident else "create_new_idea",
        "idea_id": best["idea_id"] if confident else None,
        "title": best["title"] if confident else None,
        "best_candidate": best,
        "second_candidate": second,
        "margin": margin,
        "reason": (
            "Best candidate passed the score and margin thresholds."
            if confident
            else "No candidate passed both confidence thresholds."
        ),
    }
