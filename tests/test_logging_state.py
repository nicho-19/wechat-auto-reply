import json
from pathlib import Path

import pytest

from wechat_auto_reply.logging_utils import JsonlLogger
from wechat_auto_reply.state import RuntimeState


def test_jsonl_logger_appends_event(tmp_path: Path):
    log_file = tmp_path / "logs" / "auto_reply.jsonl"
    logger = JsonlLogger(log_file)

    logger.write("reply_sent", {"chat_name": "张三", "reply": "你好"})
    logger.write("reply_skipped", {"chat_name": "李四", "reason": "rate_limited"})

    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first_event = json.loads(lines[0])
    assert first_event["event"] == "reply_sent"
    assert first_event["chat_name"] == "张三"
    assert "ts" in first_event

    second_event = json.loads(lines[1])
    assert second_event["event"] == "reply_skipped"
    assert second_event["chat_name"] == "李四"
    assert second_event["reason"] == "rate_limited"
    assert "ts" in second_event


def test_jsonl_logger_rejects_reserved_fields(tmp_path: Path):
    logger = JsonlLogger(tmp_path / "auto_reply.jsonl")

    with pytest.raises(ValueError, match="reserved"):
        logger.write("reply_sent", {"event": "override"})

    with pytest.raises(ValueError, match="reserved"):
        logger.write("reply_sent", {"ts": "override"})


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
