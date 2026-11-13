from __future__ import annotations

import unittest

from studyloop.llm_anthropic import to_anthropic_messages, to_anthropic_tools


class AdapterTest(unittest.TestCase):
    def test_system_is_extracted(self) -> None:
        system, messages = to_anthropic_messages(
            [
                {"role": "system", "content": "你是助教"},
                {"role": "user", "content": "整理笔记"},
            ]
        )
        self.assertEqual(system, "你是助教")
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"][0]["type"], "text")

    def test_assistant_tool_call_becomes_tool_use(self) -> None:
        _, messages = to_anthropic_messages(
            [
                {"role": "user", "content": "读文件"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "read_material",
                                "arguments": '{"path": "a.md"}',
                            },
                        }
                    ],
                },
            ]
        )
        block = messages[1]["content"][0]
        self.assertEqual(block["type"], "tool_use")
        self.assertEqual(block["input"], {"path": "a.md"})

    def test_consecutive_tool_results_are_merged(self) -> None:
        _, messages = to_anthropic_messages(
            [
                {"role": "assistant", "content": "调用两个工具", "tool_calls": []},
                {"role": "tool", "tool_call_id": "a", "content": "结果 A"},
                {"role": "tool", "tool_call_id": "b", "content": "结果 B"},
            ]
        )
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(len(messages[-1]["content"]), 2)
        self.assertTrue(all(b["type"] == "tool_result" for b in messages[-1]["content"]))

    def test_tools_are_converted_to_input_schema(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "save_note",
                    "description": "保存笔记",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        converted = to_anthropic_tools(tools)
        self.assertEqual(converted[0]["name"], "save_note")
        self.assertIn("input_schema", converted[0])
        self.assertNotIn("function", converted[0])


if __name__ == "__main__":
    unittest.main()
