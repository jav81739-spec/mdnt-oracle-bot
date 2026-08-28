# Arden

**Arden** is a Telegram community bot built around conversation, games, bonds, utility, and quiet surprises.

> *She doesn't announce herself. You notice.*

## Runtime

Render runs the canonical entrypoint:

```text
python bot.py
```

The existing deployment architecture, storage keys, environment variables, and Telegram bot token are intentionally preserved during the rebrand.

## Public surface

The bot exposes working commands through Telegram's command menu and `/help`.
Hidden autonomous features and owner-only controls are intentionally not listed in public help.

## Configuration

Copy `.env.example` to `.env` and provide the existing deployment values, including:

- `BOT_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (when overriding the default)
- existing Redis/Upstash settings
- existing `OWNER_ID` and group configuration

Do not commit real secrets.

## Rebrand note

The public identity is now **Arden**. Internal compatibility identifiers such as legacy Oracle-related command names, storage keys, and environment variables are retained where changing them would risk breaking existing groups or persisted data.
