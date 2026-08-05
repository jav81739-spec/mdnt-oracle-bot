# Your Telegram Bot — v1 (25 commands)

This is a working starting build. It covers one solid batch from each
category in your 87-command list: human chat, games, moderation,
utility, aesthetic/mysterious, and friendship.

## ⚠️ Before anything else
Go to @BotFather, send `/revoke`, and generate a **new** token —
the one shared earlier in chat should be treated as compromised.

## Setup

1. Install Python 3.10+
2. In this folder, run:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in:
   - `BOT_TOKEN` — your new token from @BotFather
   - `ANTHROPIC_API_KEY` — needed for real AI chat replies (optional —
     without it, `/chat` mode uses placeholder responses)
4. Run the bot:
   ```
   python bot.py
   ```
5. Add your bot to your group, make it admin (needed for mute/ban/kick),
   and test in a private/small group first.

## What's implemented (v1)
- `/chat`, `/persona` + auto language/vibe-mirroring replies
- `/quiz`, `/truth`, `/dare`, `/wyr`, `/rps`
- `/mute`, `/unmute`, `/ban`, `/kick`, `/warn`, `/rules`
- `/id`, `/info`, `/remind`
- `/oracle`, `/tarot`, `/aura`, `/confess`
- `/bestie`, `/duo`

## To activate real AI chat replies
Open `handlers/chat.py`, find the `generate_reply()` function, and
uncomment the Anthropic API example block. That's the piece that makes
the bot actually mirror language and tone like a real person.

## Next batches
The remaining ~60 commands from your full list (stats/activity log,
retention, more games, more aesthetic/friendship commands) get added
the same way — one handler file, a few functions, registered in
`bot.py`. Tell me which batch to build next.
