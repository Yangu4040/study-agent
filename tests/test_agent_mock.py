from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from studyloop.agent import Agent
from studyloop.mock import MockLLM
from studyloop.tools import Toolbox


class AgentLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "materials").mkdir()
        (self.root / "materials" / "lecture.md").write_text("# 讲义\n内容", encoding="utf-8")
        self.box = Toolbox(self.root, self.root / "data")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loop_executes_tools_until_final(self) -> None:
        llm = MockLLM(
            [
                {"name": "read_material", "args": {"path": "materials/lecture.md"}},
                {
                    "name": "save_note",
                    "args": {"title": "测试笔记", "kind": "note", "content": "# 笔记"},
                },
                {"final": "完成了"},
            ]
        )
        answer = Agent(llm, self.box, max_steps=5).run("整理笔记")
        self.assertEqual(answer, "完成了")
        self.assertEqual(len(list((self.root / "data" / "notes").glob("*.md"))), 1)
        self.assertTrue((self.root / "data" / "runs").exists())

    def test_tool_error_is_fed_back_not_crashing(self) -> None:
        llm = MockLLM(
            [
                {"name": "read_material", "args": {"path": "../outside.md"}},
                {"final": "已处理错误"},
            ]
        )
        answer = Agent(llm, self.box, max_steps=5).run("读一个不存在的文件")
        self.assertEqual(answer, "已处理错误")

    def test_max_steps_guard(self) -> None:
        script = [{"name": "get_overview", "args": {}} for _ in range(6)]
        answer = Agent(MockLLM(script), self.box, max_steps=3).run("循环")
        self.assertIn("最大步数", answer)


if __name__ == "__main__":
    unittest.main()
