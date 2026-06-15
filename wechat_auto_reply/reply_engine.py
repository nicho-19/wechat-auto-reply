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
