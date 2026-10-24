"""Run with: python -m unittest discover -s tests (from backend/)."""
import tempfile
import unittest
from pathlib import Path
from app.services import productivity as svc

class ProductivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = svc.DB_PATH
        svc.DB_PATH = Path(self.temp.name) / "test.sqlite3"
        svc.init_db()

    def tearDown(self):
        svc.DB_PATH = self.original_path
        self.temp.cleanup()

    def test_empty_day_has_no_score(self):
        self.assertIsNone(svc.summary("student-a", "2026-10-24")["score"])

    def test_daily_score_and_weekly_rollup(self):
        task = svc.create_task("student-a", "Revise graphs", "Data Structures", 25, "2026-10-24")
        svc.complete_task("student-a", task["id"], True)
        svc.create_session("student-a", "Data Structures", "2026-10-24T09:00:00+00:00", "2026-10-24T09:25:00+00:00", 1500, 1, task["id"], "")
        svc.create_assessment("student-a", "Data Structures", 5, 4, "2026-10-24T09:30:00+00:00", True)
        svc.save_reflection("student-a", "2026-10-24", "Need to revisit graph traversal")
        result = svc.summary("student-a", "2026-10-24")
        self.assertEqual(result["score"], 74)
        self.assertEqual(result["learning"]["accuracy"], 80)
        self.assertEqual(result["week"]["focused_minutes"], 25)

    def test_student_cannot_update_another_students_task(self):
        task = svc.create_task("student-a", "Revise graphs", "Data Structures", 25, "2026-10-24")
        self.assertIsNone(svc.complete_task("student-b", task["id"], True))

if __name__ == "__main__":
    unittest.main()
