from __future__ import annotations

from typing import Any

from . import database as db


def ingest_quick_note(
    initial_note: str,
    title: str | None = None,
    source: str = "text",
) -> dict[str, Any]:
    """
    Store an inbox capture under a confidently matching active idea,
    or create a new idea when confidence is insufficient.

    An explicitly supplied title always creates a new idea.
    Semantic failures also fall back to creating a new idea so that
    SQLite storage never depends on the grouping system working.
    """
    cleaned = initial_note.strip()

    if not cleaned:
        raise ValueError("Note cannot be empty")

    if title is not None and title.strip():
        return db.create_idea(
            initial_note=cleaned,
            title=title,
            source=source,
        )

    try:
        # Lazy import keeps application startup independent of the
        # embedding model and its optional runtime dependencies.
        from app.semantic.grouping import decide_grouping

        decision = decide_grouping(cleaned)
    except Exception as exc:
        print(f"Semantic grouping failed; creating a new idea: {exc}")
        return db.create_idea(initial_note=cleaned, source=source)

    best = decision.get("best_candidate")

    if decision["action"] == "add_to_existing":
        idea_id = decision["idea_id"]

        try:
            result = db.add_note(
                idea_id=idea_id,
                content=cleaned,
                source=source,
            )
        except KeyError:
            # The candidate may have disappeared between classification
            # and storage. Preserve the note by creating a new idea.
            print(
                f"Grouping candidate {idea_id} no longer exists; "
                "creating a new idea."
            )
            return db.create_idea(initial_note=cleaned, source=source)

        print(
            "Quick note grouped: "
            f"idea={idea_id} "
            f"score={best['score']:.4f} "
            f"margin={decision['margin']:.4f}"
        )
        return result

    if best is not None:
        print(
            "Quick note created as a new idea: "
            f"best_candidate={best['idea_id']} "
            f"score={best['score']:.4f} "
            f"margin={decision['margin']:.4f}"
        )
    else:
        print("Quick note created as a new idea: no active candidates")

    return db.create_idea(initial_note=cleaned, source=source)
