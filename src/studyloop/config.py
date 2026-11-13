from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv 是可选的，缺了也能用系统环境变量
    def load_dotenv(*_args, **_kwargs):
        return False


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    provider: str
    base_url: str
    api_key: str
    model: str
    workspace: Path
    home: Path
    mock: bool
    max_steps: int = 12
    max_tokens: int = 4096


def load_settings(workspace: Path | None = None, mock: bool = False) -> Settings:
    workspace = (workspace or Path.cwd()).resolve()
    # 先读工作区的 .env，再读项目根目录的 .env；系统环境变量始终优先
    load_dotenv(workspace / ".env", override=False)
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    home = Path(os.getenv("STUDYLOOP_HOME", str(workspace / "data")))
    if not home.is_absolute():
        home = workspace / home

    base_url = os.getenv("STUDYLOOP_BASE_URL", "https://api.deepseek.com/v1").strip()
    provider = os.getenv("STUDYLOOP_PROVIDER", "").strip().lower()
    if not provider:
        provider = "anthropic" if "/anthropic" in base_url else "openai"

    # anthropic 模式下允许复用系统里已有的 ANTHROPIC_API_KEY
    api_key = os.getenv("STUDYLOOP_API_KEY", "").strip()
    if not api_key and provider == "anthropic":
        api_key = (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or "").strip()

    return Settings(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=os.getenv("STUDYLOOP_MODEL", "deepseek-chat").strip(),
        workspace=workspace,
        home=home.resolve(),
        mock=mock or os.getenv("STUDYLOOP_MOCK") == "1",
        max_steps=int(os.getenv("STUDYLOOP_MAX_STEPS", "12")),
        max_tokens=int(os.getenv("STUDYLOOP_MAX_TOKENS", "4096")),
    )
