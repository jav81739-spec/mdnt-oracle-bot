"""Midnight Oracle production entrypoint."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import legacy_bot
from telegram import BotCommand, BotCommandScopeAllGroupChats
from core.ai import AIUnavailable, service as ai_service
from core.chat import generate_reply as core_generate_reply
from core.recovery import recover_deathgames
from core.health import check as health_check
from core.storage import Storage, storage
from core.utility import check_afk_mentions as core_check_afk_mentions
from core.utility import set_afk as core_set_afk
from core.autonomy import install as install_autonomy
from core.v2_features import install as install_v2_features
from core.v2_social import install as install_v2_social
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

async def _ready_probe():
    probe = Storage()
    try:
        return await health_check(probe)
    finally:
        await probe.close()

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
            self._send(200, {"status": "ok", "service": "midnight-oracle", "engine": "v2"})
            return
        if self.path == "/ready":
            try:
                result = asyncio.run(_ready_probe())
                self._send(200 if result.status == "ok" else 503, result.as_dict())
            except Exception:
                log.exception("Readiness probe failed")
                self._send(503, {"status": "degraded", "storage": "error", "bot": "unknown", "engine": "v2"})
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

legacy_bot.deathgames = deathgames_v2
_legacy_post_init = legacy_bot._post_init

async def _publish_v2_command_menu(application):
    commands = [
        BotCommand("help", "Open the Midnight V2 command deck"),
        BotCommand("hug", "Send a Midnight hug"),
        BotCommand("kiss", "Send a Midnight kiss"),
        BotCommand("pat", "Pat someone"),
        BotCommand("kick", "Playfully kick someone"),
        BotCommand("bond", "Test a Midnight pairing"),
        BotCommand("oraclepair", "Let the Oracle choose a pair"),
        BotCommand("cricket", "Play solo Midnight Cricket"),
        BotCommand("cricketduel", "Challenge someone to Cricket"),
        BotCommand("midnightplay", "Play a song in VC"),
        BotCommand("mprofile", "Open your Midnight identity"),
        BotCommand("achievements", "View your Midnight marks"),
        BotCommand("midnightevent", "Open a Midnight world event"),
        BotCommand("upgradhelp", "Read the V2 upgrade guide"),
    ]
    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
        await application.bot.set_my_commands(commands)
    except Exception:
        log.exception("Could not publish V2 command menu")

async def _post_init(application):
    try:
        await storage.start()
        await _legacy_post_init(application)
        await deathgames_v2.load_from_storage()
        recovered = await recover_deathgames(application, legacy_bot)
        install_autonomy(application)
        install_v2_features(application)
        install_v2_social(application)
        await _publish_v2_command_menu(application)
        if recovered:
            log.info("Recovered %d death-game record(s)", recovered)
        log.info("Midnight Oracle V2 autonomous, social and command layers online")
    except Exception:
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
legacy_bot.utility.set_afk = core_set_afk
legacy_bot.utility.check_afk_mentions = core_check_afk_mentions

if __name__ == "__main__":
    legacy_bot.main()
