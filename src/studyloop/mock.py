from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MockLLM:
    """按脚本返回预设的 tool_calls，用来在没有 Key 时验证循环和工具。"""

    def __init__(self, script: list[dict[str, Any]]):
        self.script = list(script)
        self.counter = 0

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.script:
            return {"role": "assistant", "content": "（mock 脚本已结束）", "tool_calls": []}

        step = self.script.pop(0)
        if "final" in step:
            return {"role": "assistant", "content": step["final"], "tool_calls": []}

        self.counter += 1
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": f"call_mock_{self.counter}",
                    "type": "function",
                    "function": {
                        "name": step["name"],
                        "arguments": json.dumps(step.get("args", {}), ensure_ascii=False),
                    },
                }
            ],
        }


NOTE = """# 从众：当多数人一起错

## 一句话总结
从众不是「没主见」，而是群体压力下的一种理性或半理性的适应策略；公开行为会从众，私下判断未必改变。

## 核心概念
- 从众：个体在真实或想象的群体压力下，改变行为或态度以贴近多数。
- 规范性影响：为了被接纳而顺从，公开场合强、私下弱。
- 信息性影响：把他人判断当作关于现实的信息，尤其在任务模糊时。

## 论证 / 推导链
1. Asch 线段实验制造了一个答案明确、群体一致错误的场景。
2. 部分被试在公开作答时跟随了错误多数。
3. 加入一个持异议的盟友后，从众率显著下降。
4. 结论：从众同时受「群体规模」与「是否存在异议者」调节。

## 易错点与边界条件
- 从众 ≠ 服从：服从有明确的命令来源，从众是同伴压力。
- 公开顺从与私下接受要分开测量，只看公开答案会高估态度改变。
- 文化差异会影响基线，但不能把实验结果直接外推到所有情境。

## 与已学内容的连接
- 与「社会助长/社会惰化」同属群体对个体行为的影响。
- 与「认知失调」相连：公开表态后，人可能调整态度以减少不适。
"""

QUIZ = """# 从众·复习题

## 主动回忆
1. 用一句话定义从众，并区分它与服从。
2. 规范性影响和信息性影响的核心差别是什么？
3. Asch 实验里，被试判断的任务为什么必须是「答案明确」的？
4. 加入一个异议者为什么会降低从众率？
5. 群体规模对从众的影响是线性的吗？
6. 公开作答与匿名作答的结果差异说明了什么？

## 应用与迁移
7. 小组作业里所有人都同意一个你怀疑有误的结论，你会怎么验证而不撕破脸？
8. 设计一个能区分「公开顺从」与「私下接受」的小实验。

## 易错辨析
9. 从众与服从：各举一例，并指出压力来源。
10. 规范性影响与信息性影响：同一个行为可能同时由两者驱动吗？

## 参考答案
1. 从众是群体压力下改变行为或态度；服从有明确命令来源，从众没有。
2. 规范性影响为获得接纳，信息性影响为获得正确信息。
3. 任务越明确，从众越难用「别人可能更懂」解释，更能暴露群体压力。
4. 异议者打破了「全体一致」的幻觉，降低了表态成本。
5. 不是；通常 3–4 人后边际效应递减。
6. 公开时从众更高，说明相当一部分是规范性顺从。
7. 先私下独立写判断，再让每人先发言，最后对照证据。
8. 公开举手后，再匿名写下真实答案，比较两者一致率。
9. 从众：跟着室友选课；服从：老师要求必须选。压力来源分别是同伴与权威。
10. 可以；模糊任务中两者常叠加。
"""


REVIEW = """## 本周完成
- 读完《社会心理学》第 3 讲，产出笔记与 10 道复习题。
- 完成 2 次主动回忆，其中「从众 vs 服从」仍然混淆。

## 未完成与原因
- 原计划读第 4 讲，实际只读了 60%。原因：周三、周四被临时任务占满。
- 复习题只做了 6 道，剩下 4 道没有安排固定时段。

## 时间去哪了
- 专业课：约 6 小时
- 副业项目：约 5 小时
- 通勤与碎片时间：约 3 小时

## 下周三个优先级
1. 补完第 4 讲，并在读完后立刻出 5 道题。
2. 把「从众 vs 服从」做成一张对比卡。
3. 固定周三 20:00—21:00 为复习时段，只做错题。

## 一个需要调整的习惯
读完材料当天就出题，不要攒到周末；隔三天再写，回忆提取的效果会明显下降。
"""


def review_script(workspace: Path) -> list[dict[str, Any]]:
    return [
        {"name": "get_overview", "args": {}},
        {"name": "list_tasks", "args": {}},
        {"name": "save_review", "args": {"content": REVIEW}},
        {
            "final": (
                "已完成本周复盘，保存在 data/reviews 下。\n"
                "下周先补第 4 讲，并把「从众 vs 服从」做成对比卡。"
            )
        },
    ]


def demo_script(workspace: Path) -> list[dict[str, Any]]:
    material = workspace / "materials" / "sample_lecture.md"
    if not material.exists():
        return [{"final": "没有找到 materials/sample_lecture.md，mock 演示已跳过。"}]
    return [
        {"name": "read_material", "args": {"path": "materials/sample_lecture.md"}},
        {
            "name": "save_note",
            "args": {"title": "从众：当多数人一起错", "kind": "note", "content": NOTE},
        },
        {
            "name": "save_note",
            "args": {"title": "从众-复习题", "kind": "quiz", "content": QUIZ},
        },
        {
            "final": (
                "已完成：读取讲义、生成笔记与 10 道复习题，均保存在 data/notes 下。\n"
                "下一步建议：先做主动回忆 6 题，再用易错辨析检查「从众 vs 服从」。"
            )
        },
    ]
