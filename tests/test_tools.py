from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from studyloop.tools import ToolError, Toolbox


class ToolboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "materials").mkdir()
        (self.root / "materials" / "lecture.md").write_text("# 讲义\n从众的定义", encoding="utf-8")
        self.box = Toolbox(self.root, self.root / "data")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_read_material(self) -> None:
        text = self.box.read_material("materials/lecture.md")
        self.assertIn("从众的定义", text)
        self.assertIn("[file] materials/lecture.md", text)

    def test_read_outside_workspace_is_rejected(self) -> None:
        outside = self.root.parent / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        try:
            with self.assertRaises(ToolError):
                self.box.read_material(str(outside))
        finally:
            outside.unlink()

    def test_save_note_and_quiz(self) -> None:
        self.box.save_note("从众笔记", "# 笔记\n内容", kind="note")
        self.box.save_note("从众复习题", "# 题目", kind="quiz")
        notes = list((self.root / "data" / "notes").glob("*.md"))
        quizzes = list((self.root / "data" / "notes" / "quizzes").glob("*.md"))
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(quizzes), 1)

    def test_task_lifecycle(self) -> None:
        self.box.add_task("复习社会心理学", due="2026-11-20", course="社心", estimate_min=60)
        listing = self.box.list_tasks()
        self.assertIn("T001", listing)
        self.assertIn("[ ]", listing)
        self.box.complete_task("T001")
        self.assertNotIn("T001", self.box.list_tasks())
        self.assertIn("[x]", self.box.list_tasks(include_done=True))

    def test_bad_due_date(self) -> None:
        with self.assertRaises(ToolError):
            self.box.add_task("坏日期", due="11/20")

    def test_review_appends(self) -> None:
        self.box.save_review("第一版", week="2026-W46")
        self.box.save_review("补充", week="2026-W46")
        text = (self.root / "data" / "reviews" / "2026-W46.md").read_text(encoding="utf-8")
        self.assertIn("第一版", text)
        self.assertIn("补充", text)
        self.assertIn("追加于", text)

    def test_search_notes(self) -> None:
        self.box.save_note("从众", "# 笔记\n规范性影响与信息性影响", kind="note")
        hits = self.box.search_notes("信息性影响")
        self.assertIn("规范性影响", hits)
        self.assertIn("没有找到", self.box.search_notes("不存在的词"))

    def test_overview(self) -> None:
        overview = self.box.get_overview()
        self.assertIn("# 学习概览", overview)
        self.assertIn("待办", overview)
        self.assertTrue((self.root / "data" / "state" / "profile.json").exists())


if __name__ == "__main__":
    unittest.main()
