"""Midnight Oracle production entrypoint."""
from __future__ import annotations

import html
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import legacy_bot
from core.ai import AIUnavailable, service as ai_service
from core.chat import generate_reply as core_generate_reply
from core.recovery import recover_deathgames
from core.health import check as health_check
from core.storage import Storage, storage
from handlers import deathgames_v2

log = logging.getLogger("midnight.entrypoint")


class _AIResponse:
    def __init__(self, text: str) -> None:
        self.text = text


async def _generate_gemini(prompt: str):
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
    uid, amount = int(uid), int(amount)
    if amount == 0:
        return await _legacy_coins(uid)
    async with storage.lock(f"legacy-economy:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired:
            log.warning("Economy lock busy for uid=%s", uid)
            return await _legacy_coins(uid)
        current = await _legacy_coins(uid)
        delta = -min(current, abs(amount)) if amount < 0 else amount
        return await storage.incrby(f"coins:{uid}", delta) if delta else current


async def _legacy_setcoins(uid: int, value: int):
    uid, target = int(uid), max(0, int(value))
    async with storage.lock(f"legacy-economy:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired:
            return await _legacy_coins(uid)
        current = await _legacy_coins(uid)
        delta = target - current
        return await storage.incrby(f"coins:{uid}", delta) if delta else current


async def _legacy_wallet(uid: int) -> int:
    value = await storage.get(f"wallet:{int(uid)}", "0")
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


async def _legacy_setwallet(uid: int, value: int):
    uid, target = int(uid), max(0, int(value))
    async with storage.lock(f"legacy-wallet:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired:
            return await _legacy_wallet(uid)
        current = await _legacy_wallet(uid)
        delta = target - current
        return await storage.incrby(f"wallet:{uid}", delta) if delta else current


# The HTTP health server runs in its own thread. It must never create or drive
# an asyncio loop from a request handler. Readiness is an explicit state that
# the bot event loop updates after storage + recovery have completed.
_ready_state = {"status": "starting", "storage": "starting", "bot": "starting"}
_ready_lock = threading.Lock()


def _set_ready_state(*, status: str, storage_status: str, bot: str) -> None:
    with _ready_lock:
        _ready_state.update({"status": status, "storage": storage_status, "bot": bot})


def _get_ready_state() -> dict[str, str]:
    with _ready_lock:
        return dict(_ready_state)


class _HealthHandler(BaseHTTPRequestHandler):
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
            state = _get_ready_state()
            self._send(200 if state["status"] == "ok" else 503, state)
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


# Activate the durable second-generation death-game engine before the legacy
# runtime registers command handlers. The old module remains in the tree as a
# rollback reference until this branch is proven stable by CI.
legacy_bot.deathgames = deathgames_v2
_legacy_post_init = legacy_bot._post_init


async def _post_init(application):
    _set_ready_state(status="starting", storage_status="starting", bot="starting")
    try:
        await storage.start()
        _set_ready_state(status="starting", storage_status="ok", bot="starting")
        await _legacy_post_init(application)
        await deathgames_v2.load_from_storage()
        recovered = await recover_deathgames(application, legacy_bot)
        if recovered:
            log.info("Recovered %d legacy death-game record(s)", recovered)
        _set_ready_state(status="ok", storage_status="ok", bot="ready")
    except Exception:
        _set_ready_state(status="degraded", storage_status="error", bot="startup_failed")
        log.exception("Startup initialization/recovery failed")
        raise


legacy_bot.html = html
legacy_bot._generate_gemini = _generate_gemini
legacy_bot._coins = _legacy_coins
legacy_bot._setcoins = _legacy_setcoins
legacy_bot._addcoins = _legacy_addcoins
legacy_bot._wallet = _legacy_wallet
legacy_bot._setwallet = _legacy_setwallet
legacy_bot._start_dummy_server = _start_health_server
legacy_bot._post_init = _post_init
legacy_bot.chat.generate_reply = core_generate_reply


if __name__ == "__main__":
    legacy_bot.main()
