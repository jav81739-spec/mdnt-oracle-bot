# Midnight Oracle — Phase 2–5 Architecture

## Phase 2 — Social

### Inside-joke engine
Observe normalized public messages, count phrase/reference recurrence across different UTC days and at least two members, reject sensitive contexts, and cap each group at 20 records. Callback selection is probability-gated and rate-limited. Never store private DM content as a group joke.

### Quiet-member recognition
Run once daily at 14:00 local time. Candidate requires 10+ interactions in 30 days, 5+ days absent, regular/known/close tier, and no ping in 14 days. Persist every ping in `absence_log`; a non-response suppresses another ping for that calendar month. Never ping during an active conversation.

### Contextual media
Media is a secondary channel, never an additional message storm. The media policy checks group/hour limits and a five-minute text-reply exclusion. Replace `None` sticker IDs in `data/sticker_map.py` with Telegram `file_id` values captured from uploaded stickers.

### Achievements
Achievements are immutable once unlocked (`UNIQUE(user_id, group_id, achievement_key)`). Evaluation is event-driven. Public badges are announced once; secret badges reveal only at unlock. No XP economy.

## Phase 3 — World

### Games
`games/game_engine.py` is the persistence boundary. One active session per group; every action updates serialized JSON state. `/endgame` is a universal escape hatch. Each game records a compact history row on termination. Game-specific modules own rules; handlers own Telegram transport.

### Secret events
Daily evaluator, maximum two weekly per group. Only public aggregate counts and group-visible behaviour are eligible. Sensitive memory, private messages, health, finances and cross-group data are prohibited. Teaser carries a `Reveal` callback; an expiry job may reveal after 30 minutes.

### Inline mode
`@OracleBot truth`, `dare`, `mood`, `roast`, `wyr`, `moment`, and `question` return `InlineQueryResultArticle`. Results contain no private memory and are safe to paste into any chat.

### Group identity
Maintain rolling humour/depth/activity aggregates in `group_identity`. Never store cross-group member identity. Use the profile only to tune tone and scheduling.

## Phase 4 — House

The Mini App is a Telegram WebApp. Frontend pages: Home, My Memory, Achievements, Group Stats, Games, Settings. `ORACLE_WEBAPP_URL` configures the deployment URL. The bot receives `sendData()` payloads through `handle_webapp_data()` and validates `initData` with HMAC-SHA256 using the Telegram WebApp algorithm.

Recommended frontend contract:

- `get_my_memory`: authenticated user, selected group, bounded memory rows.
- `forget_topic`: authenticated user only; soft-delete matching memory.
- `get_achievements`: authenticated user and group.
- `get_group_stats`: aggregate profile only.
- `get_game_history`: group-visible history only.
- `update_preference`: allow only `chatty|quiet|lurker`.

Never trust user-supplied user IDs or group IDs without authorization against the validated Telegram identity and group membership.

## Phase 5 — Legend

### Custom sticker language
Create `oracle_stickers/` with source artwork, pack manifest, and captured file IDs. Upload through Telegram sticker APIs/BotFather workflow, then populate `data/sticker_map.py`. Naming convention: `oracle_<context>_<emotion>`, e.g. `oracle_win_quiet`, `oracle_3am_awake`. Keep artwork minimal, dark, and recognizable at small size.

### Seasonal engine
Date-driven base season plus group activity signal. Examples: Ramadan mode, New Year Oracle, exam season, monsoon mood, winter quiet. Seasonal mode adjusts scheduler tone and eligible prompts; it never overrides admin quiet mode or safety/cooldowns.

### Evolving personality
Store `oracle_age_days` as derived `days since group onboarding`, not as a mutable personality blob. Unlock thresholds can be 30/90/180/365 days: richer callbacks, deeper group lore, stronger silence preference. Changes must be subtle and reversible by configuration.

### Community-wide events
Use a global event definition with opt-in group IDs. Broadcast the same public question/event key, but never share member data, memory, statistics or quotes across groups. Each group gets an independent delivery/cooldown record. Opt-out is immediate and persistent.
