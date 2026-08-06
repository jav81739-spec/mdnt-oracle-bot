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
   - `GEMINI_API_KEY` — free, no card required. Get one at
     https://aistudio.google.com/apikey (sign in with Google, click
     "Create API Key"). Needed for real AI chat replies — without it,
     `/chat` mode uses placeholder responses.
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
Just add your free `GEMINI_API_KEY` to `.env` — the code in
`handlers/chat.py` already calls Gemini automatically once the key is
set. That's the piece that makes the bot actually mirror language and
tone like a real person, and it costs nothing at normal group-chat
volume.

## Next batches
The remaining ~60 commands from your full list (stats/activity log,
retention, more games, more aesthetic/friendship commands) get added
the same way — one handler file, a few functions, registered in
`bot.py`. Tell me which batch to build next.
