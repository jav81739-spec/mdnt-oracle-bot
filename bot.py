"""Midnight Oracle production entrypoint.

This is the stable bridge during the staged rebuild. The existing feature engine
remains intact in ``legacy_bot.py`` while core services are injected here so the
migration can happen incrementally without changing the live command surface.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import legacy_bot
from core.ai import AIUnavailable, service as ai_service
from core.chat import generate_reply as core_generate_reply
from core.health import check as health_check
from core.recovery import recover_deathgames
from core.storage import storage

log = logging.getLogger("midnight.entrypoint")


class _AIResponse:
    """Compatibility response matching the legacy Gemini client's ``.text`` API."""
    def __init__(self, text: str) -> None:
        self.text = text


async def _generate_gemini(prompt: str):
    """Route every legacy AI generation call through the single async AI service."""
    try:
        return _AIResponse(await ai_service.generate(prompt, timeout=25.0))
    except AIUnavailable as exc:
        log.warning("AI unavailable: %s", exc)
        return None


async def _legacy_coins(uid: int) -> int:
    value = await storage.get(f"coins:{int(uid)}", "0")
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


async def _legacy_addcoins(uid: int, amount: int):
    """Atomic compatibility balance mutation on the existing coins:<uid> keys."""
    uid = int(uid)
    amount = int(amount)
    if amount == 0:
        return await _legacy_coins(uid)

    async with storage.lock(f"legacy-economy:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired:
            log.warning("Economy lock busy for uid=%s", uid)
            return await _legacy_coins(uid)
        current = await _legacy_coins(uid)
        if amount < 0:
            delta = -min(current, abs(amount))
        else:
            delta = amount
        if delta:
            return await storage.incrby(f"coins:{uid}", delta)
        return current


async def _legacy_setcoins(uid: int, value: int):
    uid = int(uid)
    target = max(0, int(value))
    async with storage.lock(f"legacy-economy:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired:
            return await _legacy_coins(uid)
        current = await _legacy_coins(uid)
        delta = target - current
        if delta:
            return await storage.incrby(f"coins:{uid}", delta)
        return current


async def _legacy_wallet(uid: int) -> int:
    value = await storage.get(f"wallet:{int(uid)}", "0")
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


async def _legacy_setwallet(uid: int, value: int):
    uid = int(uid)
    target = max(0, int(value))
    async with storage.lock(f"legacy-wallet:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired:
            return await _legacy_wallet(uid)
        current = await _legacy_wallet(uid)
        delta = target - current
        if delta:
            return await storage.incrby(f"wallet:{uid}", delta)
        return current


class _HealthHandler(BaseHTTPRequestHandler):
    """Cheap liveness endpoint plus dependency-aware readiness endpoint."""
    def _send(self, status: int, payload: dict[str, object]):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self._send(200, {"status": "ok", "service": "midnight-oracle"})
            return
        if self.path == "/ready":
            try:
                result = asyncio.run(health_check())
                payload = result.as_dict()
                self._send(200 if result.status == "ok" else 503, payload)
            except Exception:
                self._send(503, {"status": "degraded", "storage": "error", "bot": "unknown"})
            return
        self._send(404, {"status": "not_found"})

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, *_args):
        return


def _start_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="midnight-health").start()
    log.info("Midnight health server listening on 0.0.0.0:%s", port)
    return server


async def _post_init(application):
    """Run durable migrations/recovery after PTB has initialized the bot."""
    try:
        await storage.start()
        recovered = await recover_deathgames(application, legacy_bot)
        if recovered:
            log.info("Recovered %d pending death-game timer(s)", recovered)
    except Exception:
        log.exception("Startup recovery failed; live commands will continue")


async def _post_shutdown(application):
    """Close shared network clients cleanly on Render shutdown/redeploy."""
    await ai_service.close()
    await storage.close()


# Inject the new core into the old runtime. This is intentionally explicit so
# every remaining legacy call can be audited and migrated one subsystem at a time.
legacy_bot.html = html
legacy_bot._generate_gemini = _generate_gemini
legacy_bot._coins = _legacy_coins
legacy_bot._setcoins = _legacy_setcoins
legacy_bot._addcoins = _legacy_addcoins
legacy_bot._wallet = _legacy_wallet
legacy_bot._setwallet = _legacy_setwallet
legacy_bot._start_dummy_server = _start_health_server
# Remove the second Gemini SDK/client from handlers/chat without changing its
# public function signature. The next migration pass can then delete that
# legacy implementation entirely.
legacy_bot.chat.generate_reply = core_generate_reply


if __name__ == "__main__":
    # legacy_bot builds the Telegram Application itself, so expose lifecycle
    # hooks through its builder before entering polling.
    legacy_bot._MIDNIGHT_POST_INIT = _post_init
    legacy_bot._MIDNIGHT_POST_SHUTDOWN = _post_shutdown
    legacy_bot.main()
