from __future__ import annotations

from textwrap import shorten

import numpy as np

from app.semantic.embedder import embed_text
from app.semantic.grouping import (
    build_idea_vector,
    load_active_ideas,
)


TRIAL_MIN_SCORE = 0.44
TRIAL_MIN_MARGIN = 0.06


def normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def main() -> None:
    ideas = load_active_ideas()

    # Calculate each target vector once for the entire report.
    idea_vectors = {
        idea["idea_id"]: build_idea_vector(idea)
        for idea in ideas
    }

    grouped_count = 0
    separate_count = 0
    skipped_count = 0

    print(
        "TRIAL DRY RUN ONLY — no SQLite or FAISS changes\n"
        f"Trial minimum score:  {TRIAL_MIN_SCORE:.2f}\n"
        f"Trial minimum margin: {TRIAL_MIN_MARGIN:.2f}\n"
    )

    for source in ideas:
        if not source["notes"]:
            skipped_count += 1
            continue

        # The first note most closely represents the quick note that
        # originally caused this legacy idea to be created.
        original_note = source["notes"][0]["content"]

        query_vector = np.asarray(
            embed_text(original_note),
            dtype="float32",
        )
        query_norm = float(np.linalg.norm(query_vector))

        if query_norm == 0:
            skipped_count += 1
            continue

        query_vector /= query_norm
        candidates = []

        for target in ideas:
            # Never allow an idea to select itself.
            if target["idea_id"] == source["idea_id"]:
                continue

            target_vector = idea_vectors[target["idea_id"]]
            if target_vector is None:
                continue

            candidates.append(
                {
                    "idea_id": target["idea_id"],
                    "title": target["title"],
                    "score": float(
                        np.dot(query_vector, target_vector)
                    ),
                }
            )

        candidates.sort(
            key=lambda candidate: candidate["score"],
            reverse=True,
        )

        if not candidates:
            skipped_count += 1
            continue

        best = candidates[0]
        best_title_key = normalize_title(best["title"])

        # Exact duplicate titles should not create artificial ambiguity.
        # Compare the best match with the next distinctly titled idea.
        second = next(
            (
                candidate
                for candidate in candidates[1:]
                if normalize_title(candidate["title"])
                != best_title_key
            ),
            None,
        )

        second_score = second["score"] if second else 0.0
        margin = best["score"] - second_score

        would_group = (
            best["score"] >= TRIAL_MIN_SCORE
            and margin >= TRIAL_MIN_MARGIN
        )

        if would_group:
            grouped_count += 1
            label = "WOULD GROUP"
        else:
            separate_count += 1
            label = "KEEP SEPARATE"

        print("=" * 72)
        print(f"{label}: {source['title']}")
        print(
            "First note: "
            f"{shorten(original_note, width=100)}"
        )
        print(
            f"Best target: {best['score']:.4f}  "
            f"{best['title']}"
        )

        if second:
            print(
                f"Runner-up:   {second['score']:.4f}  "
                f"{second['title']}"
            )

        print(f"Margin:      {margin:.4f}")

    print("\n" + "=" * 72)
    print("SUMMARY")
    print(f"Would group:   {grouped_count}")
    print(f"Keep separate: {separate_count}")
    print(f"Skipped:       {skipped_count}")
    print(f"Total active:  {len(ideas)}")
    print("\nNo data was changed.")


if __name__ == "__main__":
    main()
