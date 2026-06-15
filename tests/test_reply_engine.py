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
