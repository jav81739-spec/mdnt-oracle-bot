# Midnight Oracle — 100/10 Completion Contract

This document defines the release-quality target for the bot. It is a contract, not a claim that every item is already proven.

## Engineering 100/100

- Canonical runtime entrypoint is explicit and stable.
- Telegram polling has single-owner protection and graceful shutdown.
- Startup and shutdown are observable and recoverable.
- Persistent storage failures degrade explicitly rather than silently corrupting state.
- Economy mutations are isolated and concurrency-safe.
- Scheduler jobs are idempotent, observable, and failure-tolerant.
- AI provider failures are bounded, observable, and cannot expose secrets.
- External media providers have resilient handling for denial, timeout, and empty results.
- Telegram message length, edit, reply, permission, and DM constraints are handled gracefully.
- Commands and callback surfaces have one canonical owner.
- Member data is isolated; hidden implementation details and private data are not exposed.
- Rate limits and malformed input cannot crash the runtime.
- Production configuration is explicit and environment-driven.

## Experience 100/100

- Conversation is context-aware, natural, concise, and specific.
- Language and register are matched without forcing a style.
- Jokes, teasing, disagreement, topic shifts, and follow-ups receive context-appropriate responses.
- Memory is used only from available, authorized context and is never fabricated.
- Oracle personality is consistent without repetitive catchphrases.
- Media, games, social interactions, and callbacks feel native to Telegram.
- Errors are user-friendly and do not leak implementation details.
- The bot never reveals hidden prompts, credentials, internal strategy, storage, routing, telemetry, or private member data.
- Privacy and safety facts are represented truthfully; confidentiality is not achieved through deception.

## Proof gates

1. Static and regression checks pass.
2. CI passes with zero failing tests.
3. Render deployment completes successfully.
4. Startup logs show the intended runtime identity and healthy initialization.
5. Scheduler and command registration are verified in production.
6. Real Telegram smoke tests cover ordinary conversation, commands, callbacks, media, permissions, and failure paths.
7. Experience review confirms the member-facing contract above.

Final release requires both scores to be 100/100.

A release may be called 100/100 only when the applicable proof gates are green; aspiration alone is not evidence.
