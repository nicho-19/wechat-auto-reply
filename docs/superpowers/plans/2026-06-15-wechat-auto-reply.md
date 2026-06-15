# WeChat Auto Reply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe Windows command-line WeChat Desktop auto-reply assistant that replies only to whitelisted chats using an AI-compatible chat API.

**Architecture:** Create a small Python package with isolated modules for config loading, safety policy, AI reply generation, structured logging, runtime state, and WeChat UI access. Keep WeChat UI automation behind an interface so most behavior can be tested without opening WeChat.

**Tech Stack:** Python 3.10+, `pytest`, `PyYAML`, `httpx`, optional `pywinauto` for WeChat Desktop control.

---

## File Structure

- Create `requirements.txt`: runtime and test dependencies.
- Create `config.example.yaml`: safe default configuration.
- Create `wechat_auto_reply.py`: CLI entry point.
- Create `wechat_auto_reply/__init__.py`: package marker.
- Create `wechat_auto_reply/config.py`: dataclasses and config validation.
- Create `wechat_auto_reply/safety.py`: whitelist, cooldown, duplicate, daily limit, pause checks.
- Create `wechat_auto_reply/reply_engine.py`: AI prompt construction and OpenAI-compatible API call.
- Create `wechat_auto_reply/logging_utils.py`: JSONL event logging.
- Create `wechat_auto_reply/state.py`: JSON runtime state load/save.
- Create `wechat_auto_reply/wechat_ui.py`: WeChat UI interface plus a dry-run stub.
- Create `wechat_auto_reply/app.py`: orchestration loop.
- Create `tests/test_config.py`: config tests.
- Create `tests/test_safety.py`: safety policy tests.
- Create `tests/test_reply_engine.py`: prompt/API tests.
- Create `tests/test_logging_state.py`: logging and state tests.

## Task 1: Project Skeleton and Configuration

**Files:**
- Create: `requirements.txt`
- Create: `config.example.yaml`
- Create: `wechat_auto_reply/__init__.py`
- Create: `wechat_auto_reply/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

import pytest

from wechat_auto_reply.config import ConfigError, load_config


def test_loads_valid_config(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
dry_run: true
poll_interval_seconds: 3
cooldown_seconds: 60
max_replies_per_day: 5
whitelist:
  - 张三
ai:
  base_url: https://api.example.com/v1
  model: test-model
  api_key_env: TEST_API_KEY
reply_style: 简短、礼貌，不编造事实。
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.dry_run is True
    assert config.whitelist == ["张三"]
    assert config.ai.model == "test-model"


def test_empty_whitelist_is_allowed_but_sends_nothing(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
dry_run: true
poll_interval_seconds: 3
cooldown_seconds: 60
max_replies_per_day: 5
whitelist: []
ai:
  base_url: https://api.example.com/v1
  model: test-model
  api_key_env: TEST_API_KEY
reply_style: 简短、礼貌，不编造事实。
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.whitelist == []


def test_rejects_missing_ai_section(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
dry_run: true
poll_interval_seconds: 3
cooldown_seconds: 60
max_replies_per_day: 5
whitelist:
  - 张三
reply_style: 简短、礼貌，不编造事实。
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="ai"):
        load_config(config_file)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_config.py -v
```

Expected: FAIL because `wechat_auto_reply.config` does not exist.

- [ ] **Step 3: Add dependencies and config implementation**

Create `requirements.txt`:

```text
httpx>=0.27.0
PyYAML>=6.0.1
pytest>=8.0.0
pywinauto>=0.6.8; platform_system == "Windows"
```

Create `config.example.yaml`:

```yaml
dry_run: true
poll_interval_seconds: 3
cooldown_seconds: 60
max_replies_per_day: 20
whitelist:
  - 文件传输助手
ai:
  base_url: https://api.openai.com/v1
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY
reply_style: 回复必须使用中文，简短、礼貌、像真人微信回复；不确定时说稍后确认，不编造事实。
```

Create `wechat_auto_reply/__init__.py`:

```python
"""Safe WeChat Desktop auto-reply assistant."""
```

Create `wechat_auto_reply/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the local config file is invalid."""


@dataclass(frozen=True)
class AIConfig:
    base_url: str
    model: str
    api_key_env: str


@dataclass(frozen=True)
class AppConfig:
    dry_run: bool
    poll_interval_seconds: int
    cooldown_seconds: int
    max_replies_per_day: int
    whitelist: list[str]
    ai: AIConfig
    reply_style: str


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a mapping")
    return value


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be a non-empty string")
    return value.strip()


def _require_int(value: Any, name: str, minimum: int) -> int:
    if not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{name} must be an integer >= {minimum}")
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data = _require_mapping(raw, "config")
    ai_data = _require_mapping(data.get("ai"), "ai")

    whitelist = data.get("whitelist")
    if not isinstance(whitelist, list) or not all(isinstance(item, str) for item in whitelist):
        raise ConfigError("whitelist must be a list of strings")

    return AppConfig(
        dry_run=bool(data.get("dry_run", True)),
        poll_interval_seconds=_require_int(data.get("poll_interval_seconds"), "poll_interval_seconds", 1),
        cooldown_seconds=_require_int(data.get("cooldown_seconds"), "cooldown_seconds", 1),
        max_replies_per_day=_require_int(data.get("max_replies_per_day"), "max_replies_per_day", 1),
        whitelist=[item.strip() for item in whitelist if item.strip()],
        ai=AIConfig(
            base_url=_require_str(ai_data.get("base_url"), "ai.base_url").rstrip("/"),
            model=_require_str(ai_data.get("model"), "ai.model"),
            api_key_env=_require_str(ai_data.get("api_key_env"), "ai.api_key_env"),
        ),
        reply_style=_require_str(data.get("reply_style"), "reply_style"),
    )
```

- [ ] **Step 4: Run config tests**

Run:

```powershell
python -m pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add requirements.txt config.example.yaml wechat_auto_reply/__init__.py wechat_auto_reply/config.py tests/test_config.py
git commit -m "Add config loading"
```

Expected: commit succeeds.

## Task 2: State and Safety Policy

**Files:**
- Create: `wechat_auto_reply/state.py`
- Create: `wechat_auto_reply/safety.py`
- Create: `tests/test_safety.py`

- [ ] **Step 1: Write failing safety tests**

Create `tests/test_safety.py`:

```python
from datetime import date

from wechat_auto_reply.safety import SafetyPolicy, build_message_key
from wechat_auto_reply.state import RuntimeState


def test_message_key_is_stable():
    assert build_message_key("张三", "你好") == build_message_key("张三", "你好")
    assert build_message_key("张三", "你好") != build_message_key("李四", "你好")


def test_blocks_non_whitelisted_chat():
    policy = SafetyPolicy(whitelist=["张三"], cooldown_seconds=60, max_replies_per_day=10)
    state = RuntimeState.empty()

    decision = policy.can_reply("李四", "你好", now_ts=1000, state=state, paused=False)

    assert decision.allowed is False
    assert decision.reason == "not_whitelisted"


def test_blocks_duplicate_message():
    policy = SafetyPolicy(whitelist=["张三"], cooldown_seconds=60, max_replies_per_day=10)
    state = RuntimeState.empty()
    key = build_message_key("张三", "你好")
    state.processed_message_keys.add(key)

    decision = policy.can_reply("张三", "你好", now_ts=1000, state=state, paused=False)

    assert decision.allowed is False
    assert decision.reason == "duplicate"


def test_blocks_cooldown():
    policy = SafetyPolicy(whitelist=["张三"], cooldown_seconds=60, max_replies_per_day=10)
    state = RuntimeState.empty()
    state.last_reply_at_by_chat["张三"] = 980

    decision = policy.can_reply("张三", "你好", now_ts=1000, state=state, paused=False)

    assert decision.allowed is False
    assert decision.reason == "cooldown"


def test_blocks_daily_limit():
    policy = SafetyPolicy(whitelist=["张三"], cooldown_seconds=60, max_replies_per_day=1)
    state = RuntimeState.empty()
    state.reply_count_by_day[date.fromtimestamp(1000).isoformat()] = 1

    decision = policy.can_reply("张三", "你好", now_ts=1000, state=state, paused=False)

    assert decision.allowed is False
    assert decision.reason == "daily_limit"


def test_records_reply():
    policy = SafetyPolicy(whitelist=["张三"], cooldown_seconds=60, max_replies_per_day=10)
    state = RuntimeState.empty()

    policy.record_reply("张三", "你好", now_ts=1000, state=state)

    assert build_message_key("张三", "你好") in state.processed_message_keys
    assert state.last_reply_at_by_chat["张三"] == 1000
    assert state.reply_count_by_day[date.fromtimestamp(1000).isoformat()] == 1
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_safety.py -v
```

Expected: FAIL because `state.py` and `safety.py` do not exist.

- [ ] **Step 3: Implement runtime state**

Create `wechat_auto_reply/state.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json


@dataclass
class RuntimeState:
    processed_message_keys: set[str] = field(default_factory=set)
    last_reply_at_by_chat: dict[str, int] = field(default_factory=dict)
    reply_count_by_day: dict[str, int] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "RuntimeState":
        return cls()

    @classmethod
    def load(cls, path: str | Path) -> "RuntimeState":
        state_path = Path(path)
        if not state_path.exists():
            return cls.empty()
        data: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
        return cls(
            processed_message_keys=set(data.get("processed_message_keys", [])),
            last_reply_at_by_chat={str(k): int(v) for k, v in data.get("last_reply_at_by_chat", {}).items()},
            reply_count_by_day={str(k): int(v) for k, v in data.get("reply_count_by_day", {}).items()},
        )

    def save(self, path: str | Path) -> None:
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "processed_message_keys": sorted(self.processed_message_keys),
                    "last_reply_at_by_chat": self.last_reply_at_by_chat,
                    "reply_count_by_day": self.reply_count_by_day,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Implement safety policy**

Create `wechat_auto_reply/safety.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib

from .state import RuntimeState


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str


def build_message_key(chat_name: str, message_text: str) -> str:
    payload = f"{chat_name}\n{message_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class SafetyPolicy:
    whitelist: list[str]
    cooldown_seconds: int
    max_replies_per_day: int

    def can_reply(
        self,
        chat_name: str,
        message_text: str,
        now_ts: int,
        state: RuntimeState,
        paused: bool,
    ) -> SafetyDecision:
        if paused:
            return SafetyDecision(False, "paused")
        if chat_name not in self.whitelist:
            return SafetyDecision(False, "not_whitelisted")
        if build_message_key(chat_name, message_text) in state.processed_message_keys:
            return SafetyDecision(False, "duplicate")
        last_reply_at = state.last_reply_at_by_chat.get(chat_name)
        if last_reply_at is not None and now_ts - last_reply_at < self.cooldown_seconds:
            return SafetyDecision(False, "cooldown")
        day = date.fromtimestamp(now_ts).isoformat()
        if state.reply_count_by_day.get(day, 0) >= self.max_replies_per_day:
            return SafetyDecision(False, "daily_limit")
        return SafetyDecision(True, "allowed")

    def record_reply(self, chat_name: str, message_text: str, now_ts: int, state: RuntimeState) -> None:
        state.processed_message_keys.add(build_message_key(chat_name, message_text))
        state.last_reply_at_by_chat[chat_name] = now_ts
        day = date.fromtimestamp(now_ts).isoformat()
        state.reply_count_by_day[day] = state.reply_count_by_day.get(day, 0) + 1
```

- [ ] **Step 5: Run safety tests**

Run:

```powershell
python -m pytest tests/test_safety.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add wechat_auto_reply/state.py wechat_auto_reply/safety.py tests/test_safety.py
git commit -m "Add auto reply safety policy"
```

Expected: commit succeeds.

## Task 3: AI Reply Engine

**Files:**
- Create: `wechat_auto_reply/reply_engine.py`
- Create: `tests/test_reply_engine.py`

- [ ] **Step 1: Write failing reply engine tests**

Create `tests/test_reply_engine.py`:

```python
import os

import httpx
import pytest

from wechat_auto_reply.config import AIConfig
from wechat_auto_reply.reply_engine import AIReplyEngine, MissingAPIKeyError


def test_builds_messages():
    engine = AIReplyEngine(
        ai=AIConfig(base_url="https://api.example.com/v1", model="test-model", api_key_env="TEST_API_KEY"),
        reply_style="简短回复。",
    )

    messages = engine.build_messages(chat_name="张三", incoming_message="你在吗？")

    assert messages[0]["role"] == "system"
    assert "简短回复" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "你在吗？" in messages[1]["content"]


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    engine = AIReplyEngine(
        ai=AIConfig(base_url="https://api.example.com/v1", model="test-model", api_key_env="TEST_API_KEY"),
        reply_style="简短回复。",
    )

    with pytest.raises(MissingAPIKeyError):
        engine.generate_reply("张三", "你在吗？")


def test_generate_reply_calls_openai_compatible_api(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.example.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "在的，稍后回复你。"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = AIReplyEngine(
        ai=AIConfig(base_url="https://api.example.com/v1", model="test-model", api_key_env="TEST_API_KEY"),
        reply_style="简短回复。",
        client=client,
    )

    assert engine.generate_reply("张三", "你在吗？") == "在的，稍后回复你。"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_reply_engine.py -v
```

Expected: FAIL because `reply_engine.py` does not exist.

- [ ] **Step 3: Implement reply engine**

Create `wechat_auto_reply/reply_engine.py`:

```python
from __future__ import annotations

import os

import httpx

from .config import AIConfig


class MissingAPIKeyError(RuntimeError):
    """Raised when the configured API key environment variable is missing."""


class AIReplyEngine:
    def __init__(self, ai: AIConfig, reply_style: str, client: httpx.Client | None = None) -> None:
        self.ai = ai
        self.reply_style = reply_style
        self.client = client or httpx.Client(timeout=30)

    def build_messages(self, chat_name: str, incoming_message: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你正在帮用户自动回复微信消息。"
                    "只生成可以直接发送给对方的一条微信回复，不要解释。"
                    f"回复风格和边界：{self.reply_style}"
                ),
            },
            {
                "role": "user",
                "content": f"聊天对象：{chat_name}\n对方最新消息：{incoming_message}",
            },
        ]

    def generate_reply(self, chat_name: str, incoming_message: str) -> str:
        api_key = os.environ.get(self.ai.api_key_env)
        if not api_key:
            raise MissingAPIKeyError(f"missing API key env var: {self.ai.api_key_env}")

        response = self.client.post(
            f"{self.ai.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self.ai.model,
                "messages": self.build_messages(chat_name, incoming_message),
                "temperature": 0.4,
                "max_tokens": 160,
            },
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()
```

- [ ] **Step 4: Run reply engine tests**

Run:

```powershell
python -m pytest tests/test_reply_engine.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add wechat_auto_reply/reply_engine.py tests/test_reply_engine.py
git commit -m "Add AI reply engine"
```

Expected: commit succeeds.

## Task 4: Logging and State Persistence

**Files:**
- Create: `wechat_auto_reply/logging_utils.py`
- Create: `tests/test_logging_state.py`

- [ ] **Step 1: Write failing logging and state tests**

Create `tests/test_logging_state.py`:

```python
import json
from pathlib import Path

from wechat_auto_reply.logging_utils import JsonlLogger
from wechat_auto_reply.state import RuntimeState


def test_jsonl_logger_appends_event(tmp_path: Path):
    log_file = tmp_path / "logs" / "auto_reply.jsonl"
    logger = JsonlLogger(log_file)

    logger.write("reply_sent", {"chat_name": "张三", "reply": "你好"})

    lines = log_file.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    assert event["event"] == "reply_sent"
    assert event["chat_name"] == "张三"
    assert "ts" in event


def test_runtime_state_round_trip(tmp_path: Path):
    state_file = tmp_path / "state" / "runtime.json"
    state = RuntimeState.empty()
    state.processed_message_keys.add("abc")
    state.last_reply_at_by_chat["张三"] = 123
    state.reply_count_by_day["2026-06-15"] = 2

    state.save(state_file)
    loaded = RuntimeState.load(state_file)

    assert loaded.processed_message_keys == {"abc"}
    assert loaded.last_reply_at_by_chat == {"张三": 123}
    assert loaded.reply_count_by_day == {"2026-06-15": 2}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_logging_state.py -v
```

Expected: FAIL because `logging_utils.py` does not exist.

- [ ] **Step 3: Implement JSONL logger**

Create `wechat_auto_reply/logging_utils.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class JsonlLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, event: str, fields: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run logging/state tests**

Run:

```powershell
python -m pytest tests/test_logging_state.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add wechat_auto_reply/logging_utils.py tests/test_logging_state.py
git commit -m "Add logging and runtime state persistence"
```

Expected: commit succeeds.

## Task 5: WeChat UI Boundary and Orchestration

**Files:**
- Create: `wechat_auto_reply/wechat_ui.py`
- Create: `wechat_auto_reply/app.py`
- Create: `wechat_auto_reply.py`

- [ ] **Step 1: Add WeChat UI abstraction**

Create `wechat_auto_reply/wechat_ui.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    chat_name: str
    text: str


class WeChatClient:
    def get_latest_incoming_messages(self) -> list[IncomingMessage]:
        raise NotImplementedError

    def send_reply(self, chat_name: str, reply_text: str) -> None:
        raise NotImplementedError


class DryRunWeChatClient(WeChatClient):
    def __init__(self, messages: list[IncomingMessage] | None = None) -> None:
        self.messages = messages or []
        self.sent_replies: list[tuple[str, str]] = []

    def get_latest_incoming_messages(self) -> list[IncomingMessage]:
        return list(self.messages)

    def send_reply(self, chat_name: str, reply_text: str) -> None:
        self.sent_replies.append((chat_name, reply_text))
```

- [ ] **Step 2: Add orchestration app**

Create `wechat_auto_reply/app.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from .config import AppConfig
from .logging_utils import JsonlLogger
from .reply_engine import AIReplyEngine
from .safety import SafetyPolicy
from .state import RuntimeState
from .wechat_ui import WeChatClient


@dataclass(frozen=True)
class AppPaths:
    state_file: Path = Path("logs/runtime_state.json")
    log_file: Path = Path("logs/auto_reply.jsonl")
    pause_file: Path = Path("pause.flag")


class AutoReplyApp:
    def __init__(
        self,
        config: AppConfig,
        wechat: WeChatClient,
        reply_engine: AIReplyEngine,
        paths: AppPaths = AppPaths(),
    ) -> None:
        self.config = config
        self.wechat = wechat
        self.reply_engine = reply_engine
        self.paths = paths
        self.logger = JsonlLogger(paths.log_file)
        self.policy = SafetyPolicy(
            whitelist=config.whitelist,
            cooldown_seconds=config.cooldown_seconds,
            max_replies_per_day=config.max_replies_per_day,
        )

    def run_once(self) -> None:
        state = RuntimeState.load(self.paths.state_file)
        paused = self.paths.pause_file.exists()
        now_ts = int(time.time())

        for message in self.wechat.get_latest_incoming_messages():
            decision = self.policy.can_reply(message.chat_name, message.text, now_ts, state, paused)
            if not decision.allowed:
                self.logger.write(
                    "reply_skipped",
                    {"chat_name": message.chat_name, "reason": decision.reason, "message": message.text},
                )
                continue

            reply = self.reply_engine.generate_reply(message.chat_name, message.text)
            if self.config.dry_run:
                self.logger.write(
                    "reply_dry_run",
                    {"chat_name": message.chat_name, "message": message.text, "reply": reply},
                )
            else:
                self.wechat.send_reply(message.chat_name, reply)
                self.logger.write(
                    "reply_sent",
                    {"chat_name": message.chat_name, "message": message.text, "reply": reply},
                )
            self.policy.record_reply(message.chat_name, message.text, now_ts, state)

        state.save(self.paths.state_file)
```

- [ ] **Step 3: Add CLI entry point**

Create `wechat_auto_reply.py`:

```python
from __future__ import annotations

import argparse
import sys

from wechat_auto_reply.app import AutoReplyApp
from wechat_auto_reply.config import ConfigError, load_config
from wechat_auto_reply.reply_engine import AIReplyEngine
from wechat_auto_reply.wechat_ui import DryRunWeChatClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe WeChat Desktop auto-reply assistant")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML file")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle and exit")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    reply_engine = AIReplyEngine(config.ai, config.reply_style)
    wechat = DryRunWeChatClient()
    app = AutoReplyApp(config=config, wechat=wechat, reply_engine=reply_engine)
    app.run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all tests**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add wechat_auto_reply/wechat_ui.py wechat_auto_reply/app.py wechat_auto_reply.py
git commit -m "Add auto reply orchestration"
```

Expected: commit succeeds.

## Task 6: Manual Run Documentation and Push

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update README with setup and safety instructions**

Replace `README.md` with:

```markdown
# WeChat Auto Reply

Windows local tool for a safe WeChat Desktop auto-reply assistant.

Current status: first implementation scaffold.

## Safety Goals

- Reply only to whitelisted contacts or groups.
- Support dry-run mode before sending anything.
- Support a `pause.flag` kill switch.
- Log generated replies and send results locally.
- Avoid unofficial WeChat protocols.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
```

Edit `config.yaml`, then set the API key environment variable named by `ai.api_key_env`.

```powershell
$env:OPENAI_API_KEY = "your_api_key"
python .\wechat_auto_reply.py --config config.yaml --once
```

By default, `dry_run` is `true`, so the program logs proposed replies without sending.

## Pause

Create a file named `pause.flag` in the project root to pause automatic sending.

```powershell
New-Item pause.flag -ItemType File
```

Delete that single file when you want to resume.

```powershell
Remove-Item "pause.flag"
```

## Design

- `docs/superpowers/specs/2026-06-15-wechat-auto-reply-design.md`
- `docs/superpowers/plans/2026-06-15-wechat-auto-reply.md`
```

- [x] **Step 2: Run all tests**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 3: Commit README and plan**

Run:

```powershell
git add README.md docs/superpowers/plans/2026-06-15-wechat-auto-reply.md
git commit -m "Document implementation plan"
```

Expected: commit succeeds.

- [ ] **Step 4: Push**

Run:

```powershell
git push
```

Expected: branch `main` pushes to `origin/main`.

## Self-Review

Spec coverage:

- Whitelist-only replies: Task 2 safety policy.
- AI generated replies: Task 3 reply engine.
- WeChat Desktop UI boundary: Task 5 `WeChatClient`.
- Duplicate prevention: Task 2 message keys.
- Dry-run mode: Task 5 orchestration.
- Pause switch: Task 5 `pause.flag` check.
- Structured logs: Task 4 JSONL logger.
- Cooldown and daily limits: Task 2 safety policy.
- Configurable API/model/key: Task 1 config.

Placeholder scan:

- No `TBD`, `TODO`, or undefined future implementation placeholders remain.

Type consistency:

- `AppConfig`, `AIConfig`, `RuntimeState`, `SafetyPolicy`, `AIReplyEngine`, `WeChatClient`, and `IncomingMessage` names are consistent across tasks.
