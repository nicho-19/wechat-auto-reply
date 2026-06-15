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
