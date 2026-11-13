from __future__ import annotations

from typing import Any


class LLMError(RuntimeError):
    pass


class LLM:
    """对 OpenAI 兼容接口的最小封装。换模型只改 .env，不改 Agent。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        if not api_key:
            raise LLMError(
                "缺少 STUDYLOOP_API_KEY。复制 .env.example 为 .env 并填入 Key，"
                "或先用 --mock 跑通流程。"
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("未安装 openai：pip install openai") from exc

        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=60.0, max_retries=2)
        self.model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
            )
        except Exception as exc:  # 网络、额度、模型名错误都归到这里
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        message = response.choices[0].message
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments or "{}",
                    },
                }
                for call in (message.tool_calls or [])
            ],
        }
