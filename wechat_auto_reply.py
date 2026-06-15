from __future__ import annotations

import argparse
import sys

from wechat_auto_reply.app import AutoReplyApp
from wechat_auto_reply.config import ConfigError, load_config
from wechat_auto_reply.reply_engine import AIReplyEngine
from wechat_auto_reply.wechat_ui import DryRunWeChatClient


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

    reply_engine = AIReplyEngine(config.ai, config.reply_style)
    wechat = DryRunWeChatClient()
    app = AutoReplyApp(config=config, wechat=wechat, reply_engine=reply_engine)
    app.run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
