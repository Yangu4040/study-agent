from __future__ import annotations

import json
from typing import Any, Callable

from .prompts import SYSTEM_PROMPT
from .tools import Toolbox, ToolError, record_run


class Agent:
    """最小 Agent 循环：模型决定调哪个工具 -> 执行 -> 把结果喂回去 -> 直到不再调工具。"""

    def __init__(
        self,
        llm: Any,
        toolbox: Toolbox,
        max_steps: int = 12,
        printer: Callable[[str], None] | None = None,
    ):
        self.llm = llm
        self.toolbox = toolbox
        self.max_steps = max_steps
        self.printer = printer

    def _log(self, text: str) -> None:
        if self.printer:
            self.printer(text)

    def run(self, user_input: str) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]
        schemas = self.toolbox.schemas()

        for step in range(1, self.max_steps + 1):
            message = self.llm.chat(messages, schemas)
            messages.append(message)
            calls = message.get("tool_calls") or []

            if not calls:
                answer = (message.get("content") or "").strip()
                record_run(self.toolbox.home, {"step": step, "type": "final", "content": answer})
                return answer or "（模型没有返回内容）"

            for call in calls:
                name = call["function"]["name"]
                raw_args = call["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw_args)
                    if not isinstance(args, dict):
                        raise ValueError("arguments 必须是 JSON 对象")
                    result = self.toolbox.dispatch(name, args)
                except (json.JSONDecodeError, ValueError, ToolError) as exc:
                    result = f"ERROR: {exc}"

                self._log(f"[{step}] {name}({_short(raw_args)}) -> {_short(result, 120)}")
                record_run(
                    self.toolbox.home,
                    {
                        "step": step,
                        "type": "tool",
                        "name": name,
                        "args": raw_args,
                        "result": result[:500],
                    },
                )
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": result}
                )

        answer = f"达到最大步数 {self.max_steps}，已停止。可以缩小任务或调大 STUDYLOOP_MAX_STEPS。"
        record_run(self.toolbox.home, {"type": "max_steps", "content": answer})
        return answer


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
