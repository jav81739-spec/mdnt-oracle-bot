# Midnight Oracle — Phase 2–5 Architecture

Phase 1 establishes the production boundaries: Telegram routing, bounded memory, mood estimation, persistent cooldowns, OpenAI generation, and autonomous scheduling. Later phases extend those boundaries rather than replacing them.

## Phase 2 — Social

### Inside-joke engine
A `joke_observer` consumes only messages already classified as humorous. It keeps a candidate phrase counter keyed by group/member and promotes a candidate to `inside_jokes` only after repeated appearances across separate days. Promotion requires a minimum repetition threshold and excludes secrets, private-looking content, credentials, URLs, and sensitive personal data. The reply generator receives at most one short joke hint.

### Quiet-member recognition
Track `last_seen` and meaningful interaction count. A recognition candidate requires a normal participation history followed by a configurable absence window. The engine sends at most one gentle check-in and suppresses further pings until the member returns. It never claims knowledge about why someone disappeared.

### Sticker/GIF contextual responses
Create a curated Oracle media registry with semantic tags such as `celebration`, `comfort`, `laugh`, and `surprise`. A media selector is subordinate to the same engagement governor as text replies. One media response counts as an Oracle response for cooldown purposes. The production bot uses Telegram `send_sticker`/`send_animation` with a strict per-group media budget.

### Social achievements
Achievements are event-derived records, not message-count spam. Examples: Night Owl, Chaos Agent, Philosopher, Comfort Person. Each achievement has an unlock predicate, cooldown, visibility policy, and optional private reveal. Unlock announcements are rare and can be disabled per group.

## Phase 3 — World

### Games
Use a `GameSession` table with immutable session id, host, participants, phase, deadlines, and state JSON. Truth/Dare and Would You Rather are stateless rounds; Mafia and Cricket Duel use durable state machines. Every transition is idempotent so Telegram retries cannot duplicate rounds.

### Secret events
An `event_detector` converts aggregate signals into candidate events. A daily per-group quota and confidence threshold gate delivery. Secret events expose only aggregate facts that are safe to reveal; never reveal hidden member attributes or private conversation contents.

### Inline mode
A dedicated `inline_handler` maps `@OracleBot truth`, `@OracleBot mood`, and similar queries to lightweight results. Inline generation is stateless and never receives private group memory. Deep links identify group setup without embedding secrets.

### Group identity
Maintain an aggregate profile: humour level, active hours, preferred game types, conversation density, and response tolerance. Update it using rolling windows. Never expose raw member-level statistics through the public group profile.

## Phase 4 — House

### Mini App
Telegram WebApp frontend talks to a small authenticated backend endpoint. Telegram `initData` is validated server-side before any account lookup. The UI reads a view model rather than raw database rows. Pages: Oracle profile, memory controls, achievements, group identity, and game centre.

### Personal memory dashboard
Show categories with item-level delete controls. Every memory has source timestamp and active state. `/forget` and the dashboard call the same database mutation, so privacy controls cannot diverge.

### Achievements display
Render earned achievements with unlock dates and short descriptions. Keep secret achievements hidden until unlocked. No leaderboard is required for social achievements unless a group explicitly enables one.

### Group statistics
Expose aggregate activity trends, active hours, game participation, and Oracle response rate. Do not expose individual message content or sensitive mood labels.

## Phase 5 — Legend

### Custom Oracle sticker pack
Design a restrained visual language: moon, eye, candle, quiet laugh, celebration, comfort, and “seen” motifs. Publish a dedicated sticker set and keep media selection subordinate to the delivery governor.

### Seasonal events
A rules-driven calendar contains seasonal prompts, themed games, and temporary achievements. Each event has start/end timestamps, timezone policy, group opt-out, and a strict message budget.

### Evolving personality
Personality evolves only through aggregate group preferences and explicit member feedback. Core Oracle voice remains immutable: calm, warm, slightly poetic, restrained. Evolution changes preferred humour density and interaction timing, not safety or privacy boundaries.

### Community-wide events
Use a separate event service with opt-in groups, signed event definitions, idempotent delivery keys, and per-group rate limits. Community events must never expose one group's private memory to another group.

## Reliability contract

Every phase uses the same lifecycle:

`observe → understand → score → cooldown → speak`

Provider failures are internal recovery states. They are never rendered as provider errors, stack traces, cooldown excuses, or implementation details to members. Telegram send failures are logged with correlation identifiers and retried only where idempotency is safe.
