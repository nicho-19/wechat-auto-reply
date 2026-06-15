# WeChat Auto Reply Design

## Goal

Build a Windows local tool that can automatically reply to WeChat Desktop messages for approved contacts or groups only. The first version should favor safety and controllability over broad automation.

## Scope

The tool will:

- Reply only to contacts or groups listed in a whitelist.
- Use an AI model to draft short, polite replies.
- Send replies through WeChat Desktop UI automation.
- Avoid repeated replies to the same message.
- Provide a dry-run mode that logs proposed replies without sending.
- Provide a simple pause switch through a `pause.flag` file.
- Keep a local JSONL log of observed messages, generated replies, send status, and errors.

The tool will not:

- Use unofficial WeChat protocols.
- Read or modify WeChat databases directly.
- Reply to non-whitelisted conversations.
- Attempt to bypass account security, login, or platform restrictions.

## Recommended Architecture

The project will be a small Python application with four main units:

- `config`: loads and validates local settings from `config.example.yaml` or `config.yaml`.
- `wechat_ui`: controls WeChat Desktop through Windows UI automation.
- `reply_engine`: calls the configured AI-compatible chat API and returns a candidate reply.
- `auto_reply`: coordinates polling, duplicate detection, safety checks, AI generation, sending, and logging.

The default entry point will be:

```powershell
python .\wechat_auto_reply.py
```

## Configuration

The user will configure:

- `whitelist`: exact contact or group names allowed for auto-reply.
- `dry_run`: whether replies should be logged only.
- `poll_interval_seconds`: how often to check WeChat.
- `cooldown_seconds`: minimum time between automatic replies to the same chat.
- `max_replies_per_day`: daily safety limit.
- `ai.base_url`: OpenAI-compatible API base URL.
- `ai.model`: model name.
- `ai.api_key_env`: environment variable containing the API key.
- `reply_style`: short instruction for tone and boundaries.

The first version will include a safe default style: reply in Chinese, be concise, be polite, do not invent facts, and ask the sender to wait if uncertain.

## Data Flow

1. The user logs in to WeChat Desktop.
2. The script loads configuration.
3. The script checks for `pause.flag`; if present, it logs that automation is paused.
4. The script scans recent chats in WeChat Desktop.
5. If the active or discovered chat is in the whitelist, the script reads the latest incoming message.
6. The script hashes the chat name and message content to avoid duplicate replies.
7. The script checks cooldown and daily limits.
8. The script sends the message to the AI reply engine.
9. The script either logs the reply in dry-run mode or fills and sends it in WeChat.
10. The script appends a structured log event to `logs/auto_reply.jsonl`.

## Safety Behavior

Safety controls are mandatory in the first version:

- Whitelist is required; an empty whitelist means no messages are sent.
- `dry_run` defaults to `true` in the example config.
- `pause.flag` immediately disables sending.
- Repeated messages are not reprocessed.
- A per-chat cooldown prevents rapid back-and-forth loops.
- A daily reply limit prevents runaway automation.
- AI errors, UI detection errors, and ambiguous chat states skip sending.

## Error Handling

If WeChat Desktop is not open, locked, or unreadable, the script logs the problem and exits or retries without sending. If the AI API key is missing, the script fails before attempting UI automation. If the UI automation cannot verify the target chat name, it skips sending.

## Testing

Initial tests should cover:

- Config validation.
- Whitelist decisions.
- Duplicate message detection.
- Cooldown checks.
- Daily limit checks.
- AI prompt construction without making a real API call.

Manual verification should cover:

- Dry-run mode logs replies without sending.
- Pause mode prevents sending.
- A whitelisted chat can receive one reply.
- A non-whitelisted chat is ignored.

## Implementation Notes

Use Python because it has practical Windows UI automation libraries and is easy to run locally. Prefer `pywinauto` for WeChat Desktop control and `httpx` or the OpenAI Python SDK for OpenAI-compatible chat completion calls.

Keep the first version command-line based. A graphical control panel can be added later if the core workflow proves reliable.
