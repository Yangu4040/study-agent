from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from .state import append_jsonl, load_json, save_json, stamp

MAX_READ_CHARS = 24_000
NOTE_KINDS = {"note", "quiz", "summary"}


class ToolError(RuntimeError):
    """工具执行失败。错误信息会原样回传给模型，让它自己纠正。"""


def _slug(text: str, limit: int = 40) -> str:
    cleaned = re.sub(r"[^\w一-鿿-]+", "-", text.strip())
    return cleaned.strip("-")[:limit] or "untitled"


def _iso_week(today: date | None = None) -> str:
    today = today or date.today()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


class Toolbox:
    """所有副作用都集中在这里，方便测试，也方便你审计 Agent 到底改了什么。"""

    def __init__(self, workspace: Path, home: Path):
        self.workspace = workspace.resolve()
        self.home = home.resolve()
        self.notes_dir = self.home / "notes"
        self.reviews_dir = self.home / "reviews"
        self.state_dir = self.home / "state"
        self.runs_dir = self.home / "runs"
        for folder in (self.notes_dir, self.reviews_dir, self.state_dir, self.runs_dir):
            folder.mkdir(parents=True, exist_ok=True)

    # ---------- 工具 schema：模型看到的就是这些 ----------

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_material",
                    "description": "读取工作区内的课件、讲义、论文或笔记（md/txt/csv/json，可选 pdf）。返回纯文本。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "相对工作区的路径，例如 materials/lecture03.md",
                            }
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_note",
                    "description": "把整理好的笔记、摘要或复习题保存为 Markdown 文件。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "笔记标题"},
                            "content": {"type": "string", "description": "完整 Markdown 内容"},
                            "kind": {
                                "type": "string",
                                "enum": ["note", "quiz", "summary"],
                                "description": "note=笔记，quiz=复习题，summary=摘要",
                            },
                        },
                        "required": ["title", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_task",
                    "description": "添加一条学习任务或 ddl。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "任务内容"},
                            "due": {"type": "string", "description": "截止日期，格式 YYYY-MM-DD；没有就留空"},
                            "course": {"type": "string", "description": "所属课程，可留空"},
                            "estimate_min": {"type": "integer", "description": "预计分钟数，可留空"},
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tasks",
                    "description": "列出任务。默认只列未完成的。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_done": {"type": "boolean", "description": "是否包含已完成任务"}
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "complete_task",
                    "description": "把某条任务标记为完成。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "例如 T001"}
                        },
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_review",
                    "description": "保存本周复盘。同一天重复保存会追加，不覆盖旧内容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "复盘正文（Markdown）"},
                            "week": {"type": "string", "description": "周标识，例如 2026-W46；留空则用本周"},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_notes",
                    "description": "在已保存的笔记里做关键词检索，返回命中的文件和片段。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "关键词"},
                            "limit": {"type": "integer", "description": "最多返回几条，默认 5"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_overview",
                    "description": "查看学习概览：个人信息、待办数量、本周任务、最近笔记。生成周复盘前先调用它。",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    # ---------- 分发 ----------

    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> str:
        args = args or {}
        handlers: dict[str, Callable[..., str]] = {
            "read_material": self.read_material,
            "save_note": self.save_note,
            "add_task": self.add_task,
            "list_tasks": self.list_tasks,
            "complete_task": self.complete_task,
            "save_review": self.save_review,
            "search_notes": self.search_notes,
            "get_overview": self.get_overview,
        }
        if name not in handlers:
            raise ToolError(f"未知工具：{name}")
        try:
            return handlers[name](**args)
        except TypeError as exc:
            raise ToolError(f"参数不匹配：{exc}") from exc

    # ---------- 路径安全 ----------

    def _resolve_read(self, rel: str) -> Path:
        if not rel or not rel.strip():
            raise ToolError("path 不能为空")
        candidate = Path(rel)
        candidate = candidate.resolve() if candidate.is_absolute() else (self.workspace / rel).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError("只能读取工作区内的文件，请先把材料复制进来") from exc
        if not candidate.exists():
            raise ToolError(f"文件不存在：{rel}")
        if not candidate.is_file():
            raise ToolError(f"不是文件：{rel}")
        return candidate

    # ---------- 具体工具 ----------

    def read_material(self, path: str) -> str:
        file = self._resolve_read(path)
        suffix = file.suffix.lower()
        if suffix == ".pdf":
            text = self._read_pdf(file)
        elif suffix in {".md", ".txt", ".csv", ".json", ".py", ".html", ".htm"}:
            text = file.read_text(encoding="utf-8", errors="replace")
        else:
            raise ToolError(f"暂不支持 {suffix}；请转成 md/txt，或安装可选依赖 pypdf 读取 PDF")

        total = len(text)
        truncated = total > MAX_READ_CHARS
        text = text[:MAX_READ_CHARS]
        header = f"[file] {file.relative_to(self.workspace).as_posix()}\n[chars] {total}\n"
        if truncated:
            header += f"[warn] 仅读取前 {MAX_READ_CHARS} 字，后续内容未加载\n"
        return header + "\n" + text

    @staticmethod
    def _read_pdf(file: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ToolError("读 PDF 需要可选依赖：pip install pypdf") from exc
        reader = PdfReader(str(file))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append(f"--- page {index} ---\n{page.extract_text() or ''}")
        return "\n".join(pages)

    def save_note(self, title: str, content: str, kind: str = "note") -> str:
        if not content.strip():
            raise ToolError("content 不能为空")
        kind = kind if kind in NOTE_KINDS else "note"
        folder = self.notes_dir if kind != "quiz" else self.notes_dir / "quizzes"
        folder.mkdir(parents=True, exist_ok=True)
        file = folder / f"{date.today().isoformat()}_{_slug(title)}.md"
        file.write_text(content, encoding="utf-8")
        return f"已保存：{file}（{len(content)} 字）"

    def _tasks_path(self) -> Path:
        return self.state_dir / "tasks.json"

    def _load_tasks(self) -> list[dict[str, Any]]:
        return load_json(self._tasks_path(), [])

    def add_task(
        self,
        title: str,
        due: str = "",
        course: str = "",
        estimate_min: int | str = 0,
    ) -> str:
        if not title.strip():
            raise ToolError("title 不能为空")
        if due:
            try:
                datetime.strptime(due, "%Y-%m-%d")
            except ValueError as exc:
                raise ToolError("due 必须是 YYYY-MM-DD") from exc
        try:
            estimate = int(estimate_min or 0)
        except (TypeError, ValueError):
            estimate = 0

        tasks = self._load_tasks()
        used = [int(m.group(1)) for t in tasks if (m := re.fullmatch(r"T(\d+)", t.get("id", "")))]
        task_id = f"T{(max(used) + 1) if used else 1:03d}"
        tasks.append(
            {
                "id": task_id,
                "title": title.strip(),
                "due": due,
                "course": course.strip(),
                "estimate_min": estimate,
                "done": False,
                "created_at": stamp(),
            }
        )
        save_json(self._tasks_path(), tasks)
        return f"已添加 {task_id}：{title.strip()}" + (f"（截止 {due}）" if due else "")

    def list_tasks(self, include_done: bool = False) -> str:
        tasks = self._load_tasks()
        if not include_done:
            tasks = [t for t in tasks if not t.get("done")]
        if not tasks:
            return "暂无任务。" if include_done else "暂无未完成任务。"
        tasks.sort(key=lambda t: (t.get("due") or "9999-12-31", t.get("id", "")))
        lines = []
        for task in tasks:
            mark = "x" if task.get("done") else " "
            parts = [f"{task.get('id', '?')} | [{mark}] {task.get('title', '')}"]
            if task.get("due"):
                parts.append(f"due {task['due']}")
            if task.get("course"):
                parts.append(task["course"])
            if task.get("estimate_min"):
                parts.append(f"{task['estimate_min']}min")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def complete_task(self, task_id: str) -> str:
        tasks = self._load_tasks()
        for task in tasks:
            if task.get("id") == task_id:
                if task.get("done"):
                    return f"{task_id} 已经是完成状态。"
                task["done"] = True
                task["completed_at"] = stamp()
                save_json(self._tasks_path(), tasks)
                return f"已完成 {task_id}：{task.get('title', '')}"
        raise ToolError(f"找不到任务 {task_id}")

    def save_review(self, content: str, week: str = "") -> str:
        if not content.strip():
            raise ToolError("content 不能为空")
        week = week.strip() or _iso_week()
        file = self.reviews_dir / f"{week}.md"
        if file.exists():
            old = file.read_text(encoding="utf-8")
            merged = f"{old.rstrip()}\n\n---\n\n## 追加于 {stamp('%Y-%m-%d %H:%M')}\n\n{content.strip()}\n"
        else:
            merged = content.strip() + "\n"
        file.write_text(merged, encoding="utf-8")
        return f"已保存周复盘：{file}"

    def search_notes(self, query: str, limit: int = 5) -> str:
        query = query.strip()
        if not query:
            raise ToolError("query 不能为空")
        try:
            limit = max(1, min(int(limit), 20))
        except (TypeError, ValueError):
            limit = 5

        files = sorted(self.notes_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        hits: list[str] = []
        for file in files:
            text = file.read_text(encoding="utf-8", errors="replace")
            if query.lower() not in text.lower():
                continue
            index = text.lower().find(query.lower())
            snippet = text[max(0, index - 60) : index + 120].replace("\n", " ")
            hits.append(f"{file.name}: ...{snippet}...")
            if len(hits) >= limit:
                break
        return "\n".join(hits) if hits else f"没有找到包含「{query}」的笔记。"

    def get_overview(self) -> str:
        profile_path = self.state_dir / "profile.json"
        profile = load_json(
            profile_path,
            {
                "name": "",
                "school": "",
                "major": "",
                "courses": [],
                "goals": [],
            },
        )
        if not profile_path.exists():
            save_json(profile_path, profile)

        tasks = self._load_tasks()
        open_tasks = [t for t in tasks if not t.get("done")]
        today = date.today().isoformat()
        this_week = [t for t in open_tasks if t.get("due") and t.get("due") >= today]
        notes = sorted(self.notes_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

        lines = [
            "# 学习概览",
            f"- 今天：{today}",
            f"- 本周：{_iso_week()}",
            f"- 待办：{len(open_tasks)} 条（今天及以后有截止日的 {len(this_week)} 条）",
            f"- 笔记：{len(notes)} 篇",
            "",
            "## 个人信息",
        ]
        filled = {k: v for k, v in profile.items() if v}
        lines.append(
            "、".join(f"{k}={v}" for k, v in filled.items()) if filled else "（未填写，可编辑 data/state/profile.json）"
        )
        lines.append("")
        lines.append("## 最近的笔记")
        if notes:
            lines.extend(f"- {p.relative_to(self.notes_dir)}" for p in notes[:5])
        else:
            lines.append("- 暂无")
        lines.append("")
        lines.append("## 待办清单")
        lines.append(self.list_tasks())
        return "\n".join(lines)


def record_run(home: Path, event: dict[str, Any]) -> None:
    append_jsonl(home / "runs" / f"{stamp('%Y-%m-%d')}.jsonl", event)
