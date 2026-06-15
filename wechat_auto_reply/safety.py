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
