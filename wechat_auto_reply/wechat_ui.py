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
