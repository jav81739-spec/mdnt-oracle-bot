# Midnight Oracle architecture

Midnight is organized around durable state and explicit service boundaries.

- Storage: one Upstash/Redis abstraction with bounded I/O and concurrency primitives.
- Economy: atomic balance mutations and idempotent claims.
- Relationships: durable relationship state with serialized transitions.
- Games: durable state for restart-sensitive games; lightweight games may remain stateless.
- AI: one gateway with bounded timeouts and explicit fallback behavior.
- Telegram: handlers register once through the production entrypoint.
- Scheduling: durable markers make restart/retry paths idempotent.
- Runtime: startup, readiness and shutdown are explicit lifecycle phases.

## Identity

Midnight Oracle is an original bot. Its terminology, personality, mechanics and architecture must remain its own. Publicly observable product patterns may inform design research, but private or proprietary implementations must never be copied.
