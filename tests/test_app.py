from __future__ import annotations

import json
from pathlib import Path

from wechat_auto_reply.app import AppPaths, AutoReplyApp
from wechat_auto_reply.config import AIConfig, AppConfig
from wechat_auto_reply.wechat_ui import DryRunWeChatClient, IncomingMessage


class FakeReplyEngine:
    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def generate_reply(self, chat_name: str, incoming_message: str) -> str:
        self.calls.append((chat_name, incoming_message))
        return self.reply


def make_config(*, dry_run: bool, whitelist: list[str] | None = None) -> AppConfig:
    return AppConfig(
        dry_run=dry_run,
        poll_interval_seconds=1,
        cooldown_seconds=1,
        max_replies_per_day=10,
        whitelist=whitelist or ["Alice"],
        ai=AIConfig(base_url="https://example.invalid", model="test-model", api_key_env="TEST_API_KEY"),
        reply_style="brief and friendly",
    )


def make_paths(tmp_path: Path) -> AppPaths:
    return AppPaths(
        state_file=tmp_path / "runtime_state.json",
        log_file=tmp_path / "auto_reply.jsonl",
        pause_file=tmp_path / "pause.flag",
    )


def read_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_dry_run_logs_reply_and_does_not_send(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    wechat = DryRunWeChatClient([IncomingMessage(chat_name="Alice", text="Are you there?")])
    reply_engine = FakeReplyEngine("I am here")
    app = AutoReplyApp(
        config=make_config(dry_run=True),
        wechat=wechat,
        reply_engine=reply_engine,  # type: ignore[arg-type]
        paths=paths,
    )

    app.run_once()

    assert reply_engine.calls == [("Alice", "Are you there?")]
    assert wechat.sent_replies == []
    events = read_events(paths.log_file)
    assert events == [
        {
            "ts": events[0]["ts"],
            "event": "reply_dry_run",
            "chat_name": "Alice",
            "message": "Are you there?",
            "reply": "I am here",
        }
    ]


def test_non_whitelisted_chat_logs_skipped_and_does_not_call_reply_engine(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    wechat = DryRunWeChatClient([IncomingMessage(chat_name="Mallory", text="Hello")])
    reply_engine = FakeReplyEngine()
    app = AutoReplyApp(
        config=make_config(dry_run=True, whitelist=["Alice"]),
        wechat=wechat,
        reply_engine=reply_engine,  # type: ignore[arg-type]
        paths=paths,
    )

    app.run_once()

    assert reply_engine.calls == []
    assert wechat.sent_replies == []
    event = read_events(paths.log_file)[0]
    assert event["event"] == "reply_skipped"
    assert event["chat_name"] == "Mallory"
    assert event["reason"] == "not_whitelisted"
    assert event["message"] == "Hello"


def test_non_dry_run_sends_reply_and_logs_sent(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    wechat = DryRunWeChatClient([IncomingMessage(chat_name="Alice", text="See you tomorrow")])
    reply_engine = FakeReplyEngine("See you tomorrow")
    app = AutoReplyApp(
        config=make_config(dry_run=False),
        wechat=wechat,
        reply_engine=reply_engine,  # type: ignore[arg-type]
        paths=paths,
    )

    app.run_once()

    assert reply_engine.calls == [("Alice", "See you tomorrow")]
    assert wechat.sent_replies == [("Alice", "See you tomorrow")]
    event = read_events(paths.log_file)[0]
    assert event["event"] == "reply_sent"
    assert event["chat_name"] == "Alice"
    assert event["message"] == "See you tomorrow"
    assert event["reply"] == "See you tomorrow"
