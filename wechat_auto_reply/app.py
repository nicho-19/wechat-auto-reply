from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Protocol

from .config import AppConfig
from .logging_utils import JsonlLogger
from .safety import SafetyPolicy
from .state import RuntimeState
from .wechat_ui import WeChatClient


@dataclass(frozen=True)
class AppPaths:
    state_file: Path = Path("logs/runtime_state.json")
    log_file: Path = Path("logs/auto_reply.jsonl")
    pause_file: Path = Path("pause.flag")


class ReplyEngine(Protocol):
    def generate_reply(self, chat_name: str, incoming_message: str) -> str:
        ...


class AutoReplyApp:
    def __init__(
        self,
        config: AppConfig,
        wechat: WeChatClient,
        reply_engine: ReplyEngine,
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
