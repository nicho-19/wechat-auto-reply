from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json


@dataclass
class RuntimeState:
    processed_message_keys: set[str] = field(default_factory=set)
    last_reply_at_by_chat: dict[str, int] = field(default_factory=dict)
    reply_count_by_day: dict[str, int] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "RuntimeState":
        return cls()

    @classmethod
    def load(cls, path: str | Path) -> "RuntimeState":
        state_path = Path(path)
        if not state_path.exists():
            return cls.empty()
        data: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
        return cls(
            processed_message_keys=set(data.get("processed_message_keys", [])),
            last_reply_at_by_chat={str(k): int(v) for k, v in data.get("last_reply_at_by_chat", {}).items()},
            reply_count_by_day={str(k): int(v) for k, v in data.get("reply_count_by_day", {}).items()},
        )

    def save(self, path: str | Path) -> None:
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "processed_message_keys": sorted(self.processed_message_keys),
                    "last_reply_at_by_chat": self.last_reply_at_by_chat,
                    "reply_count_by_day": self.reply_count_by_day,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
