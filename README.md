# WeChat Auto Reply

Windows local tool for a safe WeChat Desktop auto-reply assistant.

Current status: first implementation scaffold. The current CLI supports safe dry-run orchestration only; live WeChat Desktop message reading/sending is the next integration step.

The current WeChat client integration is a dry-run/stub boundary; real WeChat Desktop automation is the next integration step.

## Safety Goals

- Reply only to whitelisted contacts or groups.
- Support dry-run mode before sending anything.
- Support a `pause.flag` kill switch.
- Log generated replies and send results locally.
- Avoid unofficial WeChat protocols.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
```

Edit `config.yaml`, then set the API key environment variable named by `ai.api_key_env`.

```powershell
$env:OPENAI_API_KEY = "your_api_key"
python .\wechat_auto_reply.py --config config.yaml --once
```

By default, `dry_run` is `true`, so the program logs proposed replies without sending.

Do not set `dry_run` to `false` yet. The CLI will refuse live mode until a real WeChat Desktop UI automation client is added.

## Pause

Create a file named `pause.flag` in the project root to pause automatic sending.

```powershell
New-Item pause.flag -ItemType File
```

Delete that single file when you want to resume.

```powershell
Remove-Item "pause.flag"
```

## Design

- `docs/superpowers/specs/2026-06-15-wechat-auto-reply-design.md`
- `docs/superpowers/plans/2026-06-15-wechat-auto-reply.md`
