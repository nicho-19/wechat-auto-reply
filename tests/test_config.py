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


def test_missing_dry_run_defaults_to_true(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
poll_interval_seconds: 3
cooldown_seconds: 60
max_replies_per_day: 5
whitelist:
  - Alice
ai:
  base_url: https://api.example.com/v1
  model: test-model
  api_key_env: TEST_API_KEY
reply_style: concise
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.dry_run is True


def test_rejects_non_boolean_dry_run(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
dry_run: "false"
poll_interval_seconds: 3
cooldown_seconds: 60
max_replies_per_day: 5
whitelist:
  - Alice
ai:
  base_url: https://api.example.com/v1
  model: test-model
  api_key_env: TEST_API_KEY
reply_style: concise
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="dry_run"):
        load_config(config_file)


@pytest.mark.parametrize(
    "field",
    ["poll_interval_seconds", "cooldown_seconds", "max_replies_per_day"],
)
def test_rejects_boolean_integer_fields(tmp_path: Path, field: str):
    values = {
        "poll_interval_seconds": 3,
        "cooldown_seconds": 60,
        "max_replies_per_day": 5,
    }
    values[field] = True
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
dry_run: true
poll_interval_seconds: {str(values["poll_interval_seconds"]).lower()}
cooldown_seconds: {str(values["cooldown_seconds"]).lower()}
max_replies_per_day: {str(values["max_replies_per_day"]).lower()}
whitelist:
  - Alice
ai:
  base_url: https://api.example.com/v1
  model: test-model
  api_key_env: TEST_API_KEY
reply_style: concise
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=field):
        load_config(config_file)
