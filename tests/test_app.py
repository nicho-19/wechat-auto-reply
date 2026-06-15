from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from wechat_auto_reply.app import AppPaths, AutoReplyApp
from wechat_auto_reply.config import AIConfig, AppConfig
from wechat_auto_reply.safety import build_message_key
from wechat_auto_reply.state import RuntimeState
from wechat_auto_reply.wechat_ui import DryRunWeChatClient, IncomingMessage


def load_cli_module() -> ModuleType:
    module_path = Path(__file__).parents[1] / "wechat_auto_reply.py"
    spec = importlib.util.spec_from_file_location("wechat_auto_reply_cli", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeReplyEngine:
    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def generate_reply(self, chat_name: str, incoming_message: str) -> str:
        self.calls.append((chat_name, incoming_message))
        return self.reply


class FailingSecondReplyEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate_reply(self, chat_name: str, incoming_message: str) -> str:
        self.calls.append((chat_name, incoming_message))
        if len(self.calls) == 2:
            raise RuntimeError("boom")
        return "first reply"


class FakeLoopApp:
    def __init__(self, stop_after: int | None = None) -> None:
        self.stop_after = stop_after
        self.calls = 0

    def run_once(self) -> None:
        self.calls += 1
        if self.stop_after is not None and self.calls > self.stop_after:
            raise StopLoop


class StopLoop(Exception):
    pass


class FailingPollWeChatClient(DryRunWeChatClient):
    def get_latest_incoming_messages(self) -> list[IncomingMessage]:
        raise RuntimeError("wechat unavailable")


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


def test_run_app_once_runs_single_cycle_without_sleeping() -> None:
    cli = load_cli_module()
    app = FakeLoopApp()
    sleeps: list[int] = []

    cli.run_app(app, poll_interval_seconds=5, once=True, sleep=sleeps.append)

    assert app.calls == 1
    assert sleeps == []


def test_run_app_default_repeats_and_sleeps_between_cycles() -> None:
    cli = load_cli_module()
    app = FakeLoopApp(stop_after=2)
    sleeps: list[int] = []

    try:
        cli.run_app(app, poll_interval_seconds=7, once=False, sleep=sleeps.append)
    except StopLoop:
        pass

    assert app.calls == 3
    assert sleeps == [7, 7]


def test_build_wechat_client_allows_dry_run_only() -> None:
    cli = load_cli_module()

    client = cli.build_wechat_client(make_config(dry_run=True))

    assert isinstance(client, DryRunWeChatClient)


def test_build_wechat_client_rejects_live_mode_until_desktop_client_exists() -> None:
    cli = load_cli_module()

    try:
        cli.build_wechat_client(make_config(dry_run=False))
    except cli.UnsupportedLiveWeChatError as exc:
        assert "dry_run" in str(exc)
    else:
        raise AssertionError("live mode should be rejected until a desktop client exists")


def test_dry_run_logs_reply_and_does_not_send(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    wechat = DryRunWeChatClient([IncomingMessage(chat_name="Alice", text="Are you there?")])
    reply_engine = FakeReplyEngine("I am here")
    app = AutoReplyApp(
        config=make_config(dry_run=True),
        wechat=wechat,
        reply_engine=reply_engine,
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
        reply_engine=reply_engine,
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
        reply_engine=reply_engine,
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


def test_successful_reply_state_is_saved_before_later_message_failure(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    first = IncomingMessage(chat_name="Alice", text="first")
    second = IncomingMessage(chat_name="Bob", text="second")
    wechat = DryRunWeChatClient([first, second])
    reply_engine = FailingSecondReplyEngine()
    app = AutoReplyApp(
        config=make_config(dry_run=False, whitelist=["Alice", "Bob"]),
        wechat=wechat,
        reply_engine=reply_engine,
        paths=paths,
    )

    app.run_once()

    state = RuntimeState.load(paths.state_file)
    assert build_message_key("Alice", "first") in state.processed_message_keys
    assert build_message_key("Bob", "second") not in state.processed_message_keys
    assert state.last_reply_at_by_chat["Alice"] > 0
    assert sum(state.reply_count_by_day.values()) == 1
    events = read_events(paths.log_file)
    assert [event["event"] for event in events] == ["reply_sent", "reply_error"]
    assert events[1]["chat_name"] == "Bob"
    assert events[1]["message"] == "second"
    assert events[1]["error"] == "boom"


def test_poll_error_is_logged_without_calling_reply_engine(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    wechat = FailingPollWeChatClient()
    reply_engine = FakeReplyEngine()
    app = AutoReplyApp(
        config=make_config(dry_run=False),
        wechat=wechat,
        reply_engine=reply_engine,
        paths=paths,
    )

    app.run_once()

    assert reply_engine.calls == []
    events = read_events(paths.log_file)
    assert events[0]["event"] == "poll_error"
    assert events[0]["error"] == "wechat unavailable"
    assert RuntimeState.load(paths.state_file) == RuntimeState.empty()
