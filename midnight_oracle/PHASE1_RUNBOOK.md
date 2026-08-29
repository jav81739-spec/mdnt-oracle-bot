# Phase 1 Runbook

## Environment

Required:

- `BOT_TOKEN` — Telegram bot token
- `OPENAI_API_KEY` — OpenAI API key

Optional:

- `OPENAI_MODEL` — defaults to `gpt-4o`
- `ORACLE_DATABASE_PATH` — defaults to `midnight_oracle.sqlite3`
- `ORACLE_TIMEZONE` — defaults to `Asia/Kolkata`

## Start

Run the standalone Phase 1 application with:

```bash
python -m midnight_oracle.main
```

The first launch creates all SQLite tables automatically.

## Runtime contract

Every non-command group message enters the router. Explicit summons bypass ambient scoring. Other messages enter the Friend Engine and follow:

`observe → understand → score → cooldown → probabilistic speak`

The Friend Engine is allowed to choose silence. Provider failures return a local response and never expose provider details to Telegram members.

## Verification signals

Startup should log:

`AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on`

The test suite can be run with:

```bash
python -m unittest midnight_oracle.friend_engine_test
```
