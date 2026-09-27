import os
import tempfile
import unittest
from pathlib import Path

from app import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["OSIRIS_DB_PATH"] = str(Path(self.tmp.name) / "test.db")
        db.init_db()

    def tearDown(self):
        os.environ.pop("OSIRIS_DB_PATH", None)
        self.tmp.cleanup()

    def test_create_idea_creates_first_timeline_note(self):
        idea = db.create_idea("Build a persistent idea capture loop.")
        self.assertEqual(idea["status"], "active")
        self.assertEqual(len(idea["notes"]), 1)
        self.assertIn("persistent idea capture", idea["notes"][0]["content"])

    def test_append_note_preserves_timeline(self):
        idea = db.create_idea("Original thought")
        updated = db.add_note(idea["id"], "Follow-up thought")
        self.assertEqual([n["content"] for n in updated["notes"]], ["Original thought", "Follow-up thought"])

    def test_archive_is_non_destructive(self):
        idea = db.create_idea("Keep me")
        archived = db.update_idea(idea["id"], status="archived")
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["notes"][0]["content"], "Keep me")
        self.assertEqual(db.list_ideas(status="active"), [])
        self.assertEqual(len(db.list_ideas(status="archived")), 1)

    def test_search_checks_note_content(self):
        idea = db.create_idea("Cooking thought")
        db.add_note(idea["id"], "Remember bread flour")
        results = db.list_ideas(search="bread flour")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], idea["id"])


if __name__ == "__main__":
    unittest.main()
