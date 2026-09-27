from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database import connect, utc_now
from app.semantic.grouping import decide_grouping, load_active_ideas


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = PROJECT_ROOT / "backups" / "manual"


class UnionFind:
    def __init__(self, identifiers: list[str]):
        self.parent = {identifier: identifier for identifier in identifiers}

    def find(self, identifier: str) -> str:
        while self.parent[identifier] != identifier:
            self.parent[identifier] = self.parent[self.parent[identifier]]
            identifier = self.parent[identifier]
        return identifier

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def build_plan() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ideas = load_active_ideas()
    ideas_by_id = {idea["idea_id"]: idea for idea in ideas}
    edges = []

    for source in ideas:
        if not source["notes"]:
            continue

        decision = decide_grouping(
            source["notes"][0]["content"],
            exclude_idea_ids={source["idea_id"]},
        )

        if decision["action"] != "add_to_existing":
            continue

        best = decision["best_candidate"]
        edges.append(
            {
                "source_id": source["idea_id"],
                "source_title": source["title"],
                "target_id": best["idea_id"],
                "target_title": best["title"],
                "score": best["score"],
                "margin": decision["margin"],
            }
        )

    union_find = UnionFind(list(ideas_by_id))
    for edge in edges:
        union_find.union(edge["source_id"], edge["target_id"])

    grouped_ids: dict[str, list[str]] = {}
    for idea_id in ideas_by_id:
        root = union_find.find(idea_id)
        grouped_ids.setdefault(root, []).append(idea_id)

    incoming = Counter(edge["target_id"] for edge in edges)
    clusters = []

    for member_ids in grouped_ids.values():
        if len(member_ids) < 2:
            continue

        members = [ideas_by_id[idea_id] for idea_id in member_ids]
        canonical = sorted(
            members,
            key=lambda idea: (
                -incoming[idea["idea_id"]],
                -len(idea["notes"]),
                idea["created_at"],
                idea["idea_id"],
            ),
        )[0]

        clusters.append(
            {
                "canonical_id": canonical["idea_id"],
                "canonical_title": canonical["title"],
                "member_ids": member_ids,
                "members": [
                    {
                        "idea_id": member["idea_id"],
                        "title": member["title"],
                        "note_count": len(member["notes"]),
                    }
                    for member in members
                ],
            }
        )

    clusters.sort(key=lambda cluster: cluster["canonical_title"].casefold())
    return clusters, edges


def print_plan(clusters: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    print("REGROUPING PLAN")
    print("No ideas or notes are deleted. Merged source ideas are archived.\n")

    if not clusters:
        print("No merge clusters passed the current thresholds.")
        return

    for number, cluster in enumerate(clusters, start=1):
        print("=" * 72)
        print(f"CLUSTER {number}")
        print(f"KEEP: {cluster['canonical_title']}")
        for member in cluster["members"]:
            if member["idea_id"] == cluster["canonical_id"]:
                continue
            print(
                f"MERGE: {member['title']} "
                f"({member['note_count']} notes)"
            )

    moved_ideas = sum(len(cluster["member_ids"]) - 1 for cluster in clusters)
    print("\n" + "=" * 72)
    print(f"Clusters:          {len(clusters)}")
    print(f"Ideas to archive:  {moved_ideas}")
    print(f"Accepted edges:    {len(edges)}")


def create_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"osiris-before-regroup-{timestamp}.db"

    with connect() as source:
        with sqlite3.connect(backup_path) as destination:
            source.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()[0]

    if result != "ok":
        backup_path.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity check failed: {result}")

    return backup_path


def apply_plan(clusters: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    if not clusters:
        print("Nothing to apply.")
        return

    backup_path = create_backup()
    now = utc_now()
    moved_notes = 0

    with connect() as conn:
        for cluster in clusters:
            canonical_id = cluster["canonical_id"]

            for source_id in cluster["member_ids"]:
                if source_id == canonical_id:
                    continue

                cursor = conn.execute(
                    "UPDATE notes SET idea_id = ? WHERE idea_id = ?",
                    (canonical_id, source_id),
                )
                moved_notes += cursor.rowcount

                conn.execute(
                    """
                    UPDATE ideas
                    SET status = 'archived', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, source_id),
                )

            conn.execute(
                """
                UPDATE ideas
                SET status = 'active', updated_at = ?
                WHERE id = ?
                """,
                (now, canonical_id),
            )

    with connect() as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(
            "Live database integrity check failed after regrouping. "
            f"Backup: {backup_path}"
        )

    from app.semantic.index import build_index

    build_index()

    report_path = backup_path.with_suffix(".json")
    report_path.write_text(
        json.dumps(
            {
                "created_at": now,
                "backup_path": str(backup_path),
                "moved_notes": moved_notes,
                "clusters": clusters,
                "accepted_edges": edges,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nRegrouping completed successfully.")
    print(f"Notes moved: {moved_notes}")
    print(f"Backup: {backup_path}")
    print(f"Report: {report_path}")
    print("Database integrity: ok")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or apply conservative Osiris idea regrouping."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create a backup and apply the displayed regrouping plan.",
    )
    args = parser.parse_args()

    clusters, edges = build_plan()
    print_plan(clusters, edges)

    if args.apply:
        apply_plan(clusters, edges)
    else:
        print("\nDry run only. Re-run with --apply to perform this plan.")


if __name__ == "__main__":
    main()
