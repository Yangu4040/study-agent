# 简历与 GitHub 写法

> 用法：按投递岗位挑 2–3 条，不要全放。数字只写真实能解释的。

## 一、中文简历（项目经历）

**StudyLoop · 个人项目｜Python / LLM Agent｜2026.11**

- 独立设计并实现一个本地学习 Agent：基于 OpenAI 兼容接口的 tool-calling 循环，将课件自动转为结构化笔记与 10 题主动回忆测验，并生成周复盘。
- 设计 8 个可审计工具（读材料、写笔记、任务增删改查、笔记检索、学习概览），以「模型决策 / 代码执行」分离的方式控制副作用，内置路径穿越防护与 12 步循环上限。
- 以文件作为外部记忆（Markdown + JSON + JSONL 调用轨迹），使上下文不随使用时长膨胀，运行过程可回放；模型层可插拔，切换 DeepSeek / 通义 / GLM 仅需改 3 个环境变量。
- 提供 `--mock` 无密钥模式与 9 个单元测试，GitHub Actions 自动跑通，零框架依赖。

## 二、English resume

**StudyLoop — a minimal, inspectable study agent** · Python, LLM tool calling · 2026

- Built a CLI agent that turns lecture notes into structured study notes and active-recall quizzes, and tracks weekly tasks and reviews.
- Implemented the tool-calling loop from scratch (no LangChain): the model plans, Python executes; 8 tools cover reading, note writing, task CRUD, note search and weekly review.
- Externalized memory to files (Markdown / JSON / JSONL traces) so context stays bounded and every run is replayable; model layer is provider-agnostic via an OpenAI-compatible adapter.
- Added path-traversal protection, a max-step guard, a key-free mock mode and 9 unit tests wired to GitHub Actions.

## 三、GitHub 仓库信息

**Repository name**: `study-agent`

**About（一句话，80 字符内）**:
> A minimal, inspectable LLM study agent: notes, quizzes, weekly review.

**Topics**:
`llm` `ai-agent` `tool-calling` `python` `study-tools` `openai-compatible` `cli`

**仓库描述（中文版，放 README 顶部已有）**:
> 不用框架的 AI Agent：课件 → 笔记 → 复习题 → 周复盘，全部落成本地 Markdown。

## 四、面试怎么讲（3 分钟版）

**背景**：大二专业课材料多，读完就忘；计划写完就废。市面上的笔记工具只做存储，不做「提取练习」。

**做法**：写了一个最小 Agent。核心是一个循环——模型返回 tool call，程序执行，把结果写回上下文，直到模型不再调工具。工具只有 8 个，全部围绕「读、写、查、记」。状态不塞上下文，落到文件里。

**关键取舍**：
1. 不用 LangChain——要能讲清每一行；
2. 先不做 RAG——单份材料直接读全文更准；
3. 模型可插拔——避免焊死在一家 API 上；
4. 加 mock 模式——没 Key 也能验证流程。

**结果**：本地跑通「读讲义 → 出笔记 → 出 10 题 → 存盘」；9 个测试覆盖路径安全、任务生命周期、错误回填不崩溃；CI 通过。

**反思 / 下一步**：目前检索是关键词级，材料多了要上 BM25 或向量；错题还没有回流机制，这是下一步最值得做的。

## 五、发布到 GitHub（命令）

在 `study-agent` 目录下：

```bash
git init
git add .
git commit -m "feat: minimal study agent with tool-calling loop"
git branch -M main
git remote add origin https://github.com/<你的用户名>/study-agent.git
git push -u origin main
```

如果装了 `gh` 并已登录：

```bash
gh repo create study-agent --public --source=. --remote=origin --push
```

推送前确认 `.env` 没有被提交（`.gitignore` 已包含），`data/` 也不会进仓库。
