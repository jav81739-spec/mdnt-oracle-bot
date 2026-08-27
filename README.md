# Midnight Oracle — v2

Midnight Oracle is a Telegram group bot built around a durable, restart-safe core while preserving the established command surface.

## v2 architecture

- `bot.py` — the single production entrypoint.
- `core/storage.py` — durable Upstash Redis boundary with deterministic local fallback for tests.
- `core/economy.py` — serialized, atomic economy operations and idempotent claims.
- `core/ai.py` — one bounded Gemini HTTPS gateway with explicit unavailable behavior.
- `core/chat.py` — centralized Oracle chat generation.
- `core/game_runtime.py` — restart-safe, per-chat persistence for stateful games.
- `core/recovery.py` — startup recovery for durable game state.
- `core/utility.py` — restart-safe utility state such as AFK status.
- `core/health.py` — deterministic health/readiness checks for Render.
- `handlers/` — Telegram command handlers, migrated behind the core boundaries where state or concurrency matters.
- `legacy_bot.py` — compatibility runtime during the remaining migration; it is not a second production entrypoint.

## What v2 is protecting

The rebuild is not just a cosmetic rewrite. It targets the failures that matter after deployment:

- process restarts must not erase important game state;
- economy rewards must not be duplicated by retries;
- concurrent transfers must not corrupt balances;
- AI outages must degrade cleanly instead of hanging the bot;
- startup recovery must be repeatable;
- Render health/readiness must be deterministic;
- stateful utilities such as AFK must survive a restart;
- the production entrypoint must remain isolated from secrets and legacy Redis clients.

## Development

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m compileall -q .
python -m unittest discover -s tests -v
```

Required deployment secrets are documented in `docs/PRODUCTION_READINESS.md`. Never commit a real Telegram, Gemini, Redis, or other service credential.

## Release rule

A green test suite is necessary, not sufficient. The v2 release also requires deployment smoke tests for Telegram, Redis, Gemini, recovery, and Render health/readiness. See `docs/RELEASE_GATE.md`.

## Final runtime verification

The production entrypoint includes a token-scoped polling lease helper; deployment verification must confirm the real Render startup path acquires that lease without a `NameError`, timeout, or Telegram polling conflict.
