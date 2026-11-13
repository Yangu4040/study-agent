# StudyLoop

一个能读完的 AI Agent：把课件变成**结构化笔记 + 主动回忆题**，顺手管住每周的学习任务。

不用 LangChain，不用向量数据库，核心循环不到 80 行。适合用来理解 Agent 到底是怎么跑起来的，也适合真的拿来复习。

```bash
studyloop "把 materials/sample_lecture.md 整理成笔记和 10 道复习题"
studyloop --review      # 生成本周复盘
studyloop --tasks       # 看未完成任务
studyloop --mock        # 没有 API Key 也能跑通完整流程
```

## 它解决什么问题

大二的专业课有两个反复出现的浪费：

1. **材料读完就忘**。PDF 划了线，但没变成能自测的问题。
2. **计划写完就废**。任务散在备忘录、微信、脑子里，周末不知道时间去哪了。

StudyLoop 把这两件事压成一个闭环：**读材料 → 写笔记 → 出题 → 记任务 → 周末复盘**。所有产出都是 Markdown，存在本地，随时能改、能带走。

## 它是怎么工作的

```
你的一个句子
     │
     ▼
┌─────────────────────────────────────────────┐
│  Agent Loop (agent.py)                      │
│                                             │
│  messages ──► LLM ──► 有 tool_calls?        │
│      ▲                    │                 │
│      │                    ▼                 │
│      └──── 工具结果 ◄── Toolbox (tools.py)  │
│                           │                 │
│                           ├─ read_material  │
│                           ├─ save_note      │
│                           ├─ add_task       │
│                           ├─ list_tasks     │
│                           ├─ complete_task  │
│                           ├─ save_review    │
│                           ├─ search_notes   │
│                           └─ get_overview   │
└─────────────────────────────────────────────┘
     │
     ▼
data/notes/*.md  data/state/tasks.json  data/reviews/*.md
```

一次典型运行：

1. 你把「把这份讲义整理成笔记和复习题」发给 Agent。
2. 模型判断需要原文，返回一个 `read_material` 的 tool call。
3. 程序执行工具，把文件内容作为 `role: tool` 的消息塞回对话。
4. 模型基于原文写笔记，返回 `save_note`。
5. 再返回一次 `save_note(kind="quiz")`。
6. 模型不再调用工具，输出最终答复，循环结束。

## 四个原理，对应四段代码

### 1. Tool Calling：模型不执行，只「点菜」

模型本身不能读文件、不能写文件。它只能输出一个结构化请求：

```json
{"name": "read_material", "arguments": {"path": "materials/lecture.md"}}
```

真正执行的是 `Toolbox.dispatch()`。这条边界很重要：**模型负责决策，代码负责副作用**。所以你能审计它到底改了什么，也能在工具里加权限控制。

对应：`tools.py` 的 `schemas()` 与 `dispatch()`。

### 2. Agent Loop：不是一次问答，而是一个状态机

普通 Chatbot 是 `输入 → 输出`。Agent 是：

```
while 还有工具调用 and 步数 < 上限:
    模型决策 → 执行工具 → 把结果写回上下文
```

每一轮，模型看到的都是「系统提示 + 用户请求 + 之前的工具结果」。它根据新信息决定下一步。这就是 ReAct（Reason + Act）的最小形态。

对应：`agent.py` 的 `run()`。

### 3. 文件即记忆：状态外置，不塞进上下文

任务存在 `data/state/tasks.json`，笔记存在 `data/notes/`，每次运行的事件流存在 `data/runs/*.jsonl`。

这样做的好处：

- 上下文窗口不会被历史记录撑爆；
- 你能直接用编辑器改状态，Agent 下次读到的就是改后的；
- 出问题能回放：哪一步调了什么工具、返回了什么。

对应：`state.py` 与 `tools.py` 的 `_load_tasks()` / `save_json()`。

### 4. 模型可插拔：Agent 不绑定厂商

`llm.py` 只依赖 OpenAI 兼容接口。换 DeepSeek、通义、GLM、Kimi，只改 `.env` 三行：

```env
STUDYLOOP_BASE_URL=https://api.deepseek.com/v1
STUDYLOOP_MODEL=deepseek-chat
STUDYLOOP_API_KEY=sk-...
```

Agent 逻辑、工具、提示词一行不动。这是把「模型」当成可替换组件，而不是把产品焊死在某一家身上。

Anthropic 原生接口（Claude，以及 DeepSeek、Kimi 等提供的 `/anthropic` 兼容端点）也支持：

```env
STUDYLOOP_PROVIDER=anthropic
STUDYLOOP_BASE_URL=https://api.deepseek.com/anthropic
STUDYLOOP_MODEL=deepseek-chat
STUDYLOOP_API_KEY=sk-...
```

`llm_anthropic.py` 负责两件容易出错的事：把 system 从消息里拆出来；把连续的 `tool_result` 合并进一条 user 消息，紧跟对应的 `tool_use`。需要 `pip install anthropic`。

## 快速开始

需要 Python 3.10+。

```bash
git clone https://github.com/Yangu4040/study-agent.git
cd study-agent

# 方式一：uv（推荐）
uv venv
uv pip install -e .

# 方式二：pip
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -e .
```

复制配置并填入 Key：

```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
```

先不花钱验证一遍流程：

```bash
studyloop --mock
```

再接真实模型：

```bash
studyloop "读取 materials/sample_lecture.md，整理成笔记，再出 10 道复习题"
studyloop --review
studyloop --tasks
```

## 目录结构

```
study-agent/
├── src/studyloop/
│   ├── agent.py      # 循环：模型 → 工具 → 回填 → 直到结束
│   ├── tools.py      # 8 个工具 + 路径安全 + 任务/笔记存储
│   ├── llm.py        # OpenAI 兼容接口封装
│   ├── llm_anthropic.py  # Anthropic Messages API 适配层
│   ├── prompts.py    # 系统提示词与固定输出结构
│   ├── mock.py       # 无 Key 演示脚本
│   ├── config.py     # 环境变量与路径
│   ├── state.py      # JSON / JSONL 读写
│   └── cli.py        # 命令行入口
├── materials/        # 放你的课件、论文、讲义
├── tests/            # 纯标准库 unittest
├── data/             # 运行时生成（已 gitignore）
│   ├── notes/        # 笔记与复习题
│   ├── reviews/      # 周复盘
│   ├── state/        # tasks.json / profile.json
│   └── runs/         # 每次运行的调用轨迹
└── .github/workflows/ci.yml
```

## 设计取舍

**为什么不用 LangChain？**
这个项目的目的是让你能把每一行都讲清楚。引入框架后，出问题时你面对的是框架的抽象层，而不是自己的代码。80 行的循环足够支撑 8 个工具，也足够你改造。

**为什么先不做 RAG？**
RAG 解决的是「资料太多，一次塞不进上下文」。当前场景是单份讲义，直接读全文更准，也少一层检索失败的可能。等材料库到几十份，再加 `search_notes` 的语义检索版本。

**为什么坚持写文件？**
对话是易失的，文件是可积累的。复习这件事的价值在「下周还能翻到」，不在「这次回答很漂亮」。

**为什么有 `--mock`？**
让你在没有 Key、没有网络、甚至不想花钱的时候，也能验证循环、工具、路径安全是否正常。测试也依赖它。

## 测试

```bash
python -m unittest discover -s tests -v
```

覆盖：路径穿越拒绝、笔记与题目落盘、任务增删改查、周复盘追加、错误回填不崩溃、最大步数保护。

## Roadmap

- [ ] `search_notes` 加 BM25 / 向量检索，支持几十份材料
- [ ] 错题本：把答错的题自动回收到下周复习
- [ ] 接入日历（ICS），把任务写进系统日历
- [ ] 多模型对照：同一份材料让两个模型出题，比较覆盖度
- [ ] Web UI（FastAPI + 单页），但不引入前端框架

## License

MIT
