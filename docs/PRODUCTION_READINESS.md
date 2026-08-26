# Midnight Oracle production readiness

## Release gate

The bot must pass the repository CI suite before merge. Production deployment additionally requires valid Render, Telegram and Upstash configuration.

## Required environment

- `BOT_TOKEN`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `GEMINI_API_KEY`
- optional `GEMINI_MODEL`

Secrets must exist only in the deployment secret store/environment. Never commit real credentials or place credentials in example files.

## Startup

The process must initialize storage, recover durable scheduled state, start the Telegram application once, and expose the health/readiness endpoint expected by the deployment platform.

## Shutdown

SIGTERM/SIGINT must stop background tasks and the Telegram application cleanly without corrupting durable state.

## Release checklist

- [ ] CI install succeeds
- [ ] dependency integrity check succeeds
- [ ] Python compilation succeeds
- [ ] regression suite succeeds
- [ ] no real secrets in tracked files
- [ ] Telegram bot token rotated if previously exposed
- [ ] Gemini key rotated if previously exposed
- [ ] Render environment variables configured
- [ ] Upstash connectivity verified in deployment
- [ ] Telegram polling/webhook mode is configured exactly once
- [ ] health endpoint responds after startup
- [ ] logs contain no credentials

A green CI run is necessary but does not prove connectivity to a user's live external services.
