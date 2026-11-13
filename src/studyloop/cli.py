from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent import Agent
from .config import load_settings
from .llm import LLM, LLMError
from .llm_anthropic import AnthropicLLM
from .mock import MockLLM, demo_script, review_script
from .prompts import DEMO_PROMPT, REVIEW_PROMPT
from .tools import Toolbox


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="studyloop",
        description="把课件变成笔记与复习题，并管理每周学习任务。",
    )
    parser.add_argument("prompt", nargs="*", help="用一句话告诉它要做什么")
    parser.add_argument("--review", action="store_true", help="生成本周复盘")
    parser.add_argument("--tasks", action="store_true", help="只列出未完成任务，不调用模型")
    parser.add_argument("--mock", action="store_true", help="不调用模型，用脚本跑通工具循环")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印每一步工具调用")
    parser.add_argument("--workspace", default=None, help="工作区目录，默认当前目录")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace) if args.workspace else Path.cwd()
    settings = load_settings(workspace, mock=args.mock)
    toolbox = Toolbox(settings.workspace, settings.home)

    if args.tasks:
        print(toolbox.dispatch("list_tasks", {}))
        return 0

    prompt = " ".join(args.prompt).strip()
    if args.review:
        prompt = REVIEW_PROMPT
    if not prompt:
        prompt = DEMO_PROMPT

    if settings.mock:
        script = review_script(settings.workspace) if args.review else demo_script(settings.workspace)
        llm = MockLLM(script)
        print("[mock] 未调用真实模型，仅验证工具调用循环。\n", file=sys.stderr)
    else:
        try:
            if settings.provider == "anthropic":
                llm = AnthropicLLM(
                    settings.base_url, settings.api_key, settings.model, settings.max_tokens
                )
            else:
                llm = LLM(settings.base_url, settings.api_key, settings.model)
        except LLMError as exc:
            print(f"配置错误：{exc}", file=sys.stderr)
            return 2
        print(
            f"[model] {settings.provider} | {settings.model} @ {settings.base_url}",
            file=sys.stderr,
        )

    printer = (lambda text: print(text, file=sys.stderr)) if args.verbose else None
    agent = Agent(llm, toolbox, max_steps=settings.max_steps, printer=printer)

    try:
        answer = agent.run(prompt)
    except LLMError as exc:
        print(f"模型调用失败：{exc}", file=sys.stderr)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
