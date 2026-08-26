# Midnight Oracle — final release gate

This branch is not ready for production merely because unit tests pass. The release gate requires all of the following evidence:

- `main` remains untouched.
- `bot.py` is the only production entrypoint.
- `legacy_bot.py` is compatibility/runtime implementation only; it is not a second entrypoint.
- Stateful handlers use the durable storage boundary where restart safety matters.
- Economy mutations are serialized/atomic and reward operations are idempotent.
- DeathGames and other restart-sensitive games recover after process restart.
- AI has one gateway, bounded timeouts and explicit unavailable behavior.
- Moderation failures are observable and do not silently corrupt state.
- Scheduler/startup/recovery paths are idempotent.
- Render health/readiness endpoints are deterministic.
- No tracked example/config file contains a real credential.
- CI passes on the exact release commit: installation, dependency check, compilation and full regression suite.
- The branch diff against `main` has been reviewed for accidental feature loss.

Human-only production gates:

1. Rotate any credential that was ever committed to repository history.
2. Configure fresh secrets in Render/Upstash/Gemini.
3. Start the deployed bot and perform Telegram smoke tests.
4. Verify `/health` and `/ready` from the deployed service.
5. Verify a real Redis write/read, economy transaction, scheduled recovery and Gemini request.

Until the human-only gates are completed, the code can be CI-green but must not be represented as live-production verified.
