from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class JsonlLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, event: str, fields: dict[str, Any]) -> None:
        reserved_fields = {"event", "ts"} & fields.keys()
        if reserved_fields:
            reserved = ", ".join(sorted(reserved_fields))
            raise ValueError(f"fields contain reserved JSONL metadata keys: {reserved}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
