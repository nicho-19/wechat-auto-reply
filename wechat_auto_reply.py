from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
import time

from wechat_auto_reply.app import AutoReplyApp
from wechat_auto_reply.config import ConfigError, load_config
from wechat_auto_reply.reply_engine import AIReplyEngine
from wechat_auto_reply.wechat_ui import DryRunWeChatClient, WeChatClient


class UnsupportedLiveWeChatError(RuntimeError):
    """Raised when config requests live WeChat automation that is not wired yet."""


def run_app(
    app: AutoReplyApp,
    poll_interval_seconds: int,
    once: bool,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    while True:
        app.run_once()
        if once:
            return
        sleep(poll_interval_seconds)


def build_wechat_client(config) -> WeChatClient:
    if config.dry_run:
        return DryRunWeChatClient()
    raise UnsupportedLiveWeChatError(
        "dry_run is false, but the live WeChat Desktop client is not implemented yet. "
        "Set dry_run: true until the UI automation client is added."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe WeChat Desktop auto-reply assistant")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML file")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle and exit")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    try:
        wechat = build_wechat_client(config)
    except UnsupportedLiveWeChatError as exc:
        print(f"WeChat client error: {exc}", file=sys.stderr)
        return 3

    reply_engine = AIReplyEngine(config.ai, config.reply_style)
    app = AutoReplyApp(config=config, wechat=wechat, reply_engine=reply_engine)
    run_app(app, poll_interval_seconds=config.poll_interval_seconds, once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
