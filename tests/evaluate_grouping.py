from app.semantic.grouping import find_best_ideas


EXAMPLES = [
    (
        "CLEAR EXISTING IDEA",
        "I should make sure the Osiris server automatically recovers after a crash.",
    ),
    (
        "AMBIGUOUS",
        "I want to improve how I use my phone and laptop together.",
    ),
    (
        "LIKELY NEW IDEA",
        "I want to try making homemade pizza dough.",
    ),
]


def main() -> None:
    for label, note_text in EXAMPLES:
        print()
        print("=" * 72)
        print(label)
        print(f"Incoming note: {note_text}")
        print()

        candidates = find_best_ideas(note_text, limit=5)

        if not candidates:
            print("No active idea candidates.")
            continue

        for position, candidate in enumerate(candidates, start=1):
            print(
                f"{position}. {candidate['score']:.4f}  "
                f"{candidate['title']}  "
                f"({candidate['note_count']} notes)"
            )

        if len(candidates) >= 2:
            margin = candidates[0]["score"] - candidates[1]["score"]
            print(f"\nBest-to-second margin: {margin:.4f}")


if __name__ == "__main__":
    main()
