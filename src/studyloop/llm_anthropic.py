from __future__ import annotations

import json
from typing import Any

from .llm import LLMError


def to_anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """把 Agent 的中立消息格式转成 Anthropic Messages 格式。

    两条规则容易踩坑：
    1. system 不是消息，要单独作为 system 参数；
    2. 每个 tool_result 必须放在紧跟 tool_use 的 user 消息里，连续结果要合并。
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        if role == "system":
            system_parts.append(str(message.get("content") or ""))
            continue

        if role == "user":
            out.append(
                {"role": "user", "content": [{"type": "text", "text": str(message.get("content") or "")}]}
            )
            continue

        if role == "assistant":
            raw = message.get("_raw")
            if raw:
                out.append({"role": "assistant", "content": raw})
                continue
            blocks: list[dict[str, Any]] = []
            if message.get("content"):
                blocks.append({"type": "text", "text": str(message["content"])})
            for call in message.get("tool_calls") or []:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": _safe_json(call["function"].get("arguments")),
                    }
                )
            out.append({"role": "assistant", "content": blocks})
            continue

        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": message.get("tool_call_id", ""),
                "content": str(message.get("content") or ""),
            }
            if out and out[-1]["role"] == "user" and all(
                item.get("type") == "tool_result" for item in out[-1]["content"]
            ):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})

    return "\n\n".join(part for part in system_parts if part), out


def to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools:
        fn = tool.get("function", {})
        converted.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return converted


def _safe_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class AnthropicLLM:
    """Anthropic Messages API 适配器，对外暴露与 LLM 相同的 chat() 接口。"""

    def __init__(self, base_url: str, api_key: str, model: str, max_tokens: int = 4096):
        if not api_key:
            raise LLMError(
                "缺少 API Key。设置 STUDYLOOP_API_KEY，或复用 ANTHROPIC_API_KEY。"
            )
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise LLMError("未安装 anthropic：pip install anthropic") from exc

        self.client = Anthropic(base_url=base_url, api_key=api_key, timeout=120.0, max_retries=2)
        self.model = model
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        system, converted = to_anthropic_messages(messages)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system or None,
                messages=converted,
                tools=to_anthropic_tools(tools),
            )
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        raw_blocks: list[dict[str, Any]] = []
        for block in response.content:
            block_type = getattr(block, "type", "")
            raw_blocks.append(_dump_block(block))
            if block_type == "text":
                text_parts.append(block.text)
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input, ensure_ascii=False),
                        },
                    }
                )

        return {
            "role": "assistant",
            "content": "".join(text_parts),
            "tool_calls": tool_calls,
            "_raw": raw_blocks,
        }


def _dump_block(block: Any) -> dict[str, Any]:
    """保留 thinking 的 signature，避免多轮工具调用时丢失签名。"""
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return {"type": getattr(block, "type", "text"), "text": getattr(block, "text", "")}
