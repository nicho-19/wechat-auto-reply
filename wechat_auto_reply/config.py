from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the local config file is invalid."""


@dataclass(frozen=True)
class AIConfig:
    base_url: str
    model: str
    api_key_env: str


@dataclass(frozen=True)
class AppConfig:
    dry_run: bool
    poll_interval_seconds: int
    cooldown_seconds: int
    max_replies_per_day: int
    whitelist: list[str]
    ai: AIConfig
    reply_style: str


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a mapping")
    return value


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be a non-empty string")
    return value.strip()


def _require_int(value: Any, name: str, minimum: int) -> int:
    if not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{name} must be an integer >= {minimum}")
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data = _require_mapping(raw, "config")
    ai_data = _require_mapping(data.get("ai"), "ai")

    whitelist = data.get("whitelist")
    if not isinstance(whitelist, list) or not all(isinstance(item, str) for item in whitelist):
        raise ConfigError("whitelist must be a list of strings")

    return AppConfig(
        dry_run=bool(data.get("dry_run", True)),
        poll_interval_seconds=_require_int(data.get("poll_interval_seconds"), "poll_interval_seconds", 1),
        cooldown_seconds=_require_int(data.get("cooldown_seconds"), "cooldown_seconds", 1),
        max_replies_per_day=_require_int(data.get("max_replies_per_day"), "max_replies_per_day", 1),
        whitelist=[item.strip() for item in whitelist if item.strip()],
        ai=AIConfig(
            base_url=_require_str(ai_data.get("base_url"), "ai.base_url").rstrip("/"),
            model=_require_str(ai_data.get("model"), "ai.model"),
            api_key_env=_require_str(ai_data.get("api_key_env"), "ai.api_key_env"),
        ),
        reply_style=_require_str(data.get("reply_style"), "reply_style"),
    )
