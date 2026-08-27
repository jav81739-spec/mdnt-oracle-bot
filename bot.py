"""Midnight Oracle production entrypoint."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import legacy_bot
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators
from core.ai import AIUnavailable, service as ai_service
from core.chat import generate_reply as core_generate_reply
from core.recovery import recover_deathgames
from core.health import check as health_check
from core.storage import Storage, storage
from core.utility import check_afk_mentions as core_check_afk_mentions
from core.utility import set_afk as core_set_afk
from core.autonomy import install as install_autonomy
from core.cricket_v2 import install as install_cricket_v2
from core.deathgames_v2_install import install as install_deathgames_v2
from core.v2_features import install as install_v2_features
from core.v2_help import install as install_v2_help
from core.v2_social2 import install as install_v2_social
from core.v2_autonomous import install as install_v2_autonomous
from core.midnight_social_intelligence import install as install_social_intelligence
from core.v2_bond_signal import install as install_bond_signal
from core.vc_player import install as install_vc_player, player as vc_player
from core.owner_tools import install as install_owner_tools, publish_owner_menu
from handlers import deathgames_v2

log = logging.getLogger("midnight.entrypoint")

_POLLING_LEASE_KEY = "midnight:telegram:polling-lease:v2"
_POLLING_LEASE_TTL = 90
_POLLING_LEASE_WAIT = 150

class _AIResponse:
    def __init__(self, text: str) -> None: self.text = text

async def _generate_gemini(prompt: str):
    try: return _AIResponse(await ai_service.generate(prompt, timeout=25.0))
    except AIUnavailable as exc:
        log.warning("AI unavailable: %s", exc); return None

async def _legacy_coins(uid: int) -> int:
    value = await storage.get(f"coins:{int(uid)}", "0")
    try: return max(0, int(value or 0))
    except (TypeError, ValueError): return 0

async def _legacy_addcoins(uid: int, amount: int):
    uid, amount = int(uid), int(amount)
    if amount == 0: return await _legacy_coins(uid)
    async with storage.lock(f"legacy-economy:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired: return await _legacy_coins(uid)
        current = await _legacy_coins(uid); delta = -min(current, abs(amount)) if amount < 0 else amount
        return await storage.incrby(f"coins:{uid}", delta) if delta else current

async def _legacy_setcoins(uid: int, value: int):
    uid, target = int(uid), max(0, int(value))
    async with storage.lock(f"legacy-economy:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired: return await _legacy_coins(uid)
        current = await _legacy_coins(uid); delta = target - current
        return await storage.incrby(f"coins:{uid}", delta) if delta else current

async def _legacy_wallet(uid: int) -> int:
    value = await storage.get(f"wallet:{int(uid)}", "0")
    try: return max(0, int(value or 0))
    except (TypeError, ValueError): return 0

async def _legacy_setwallet(uid: int, value: int):
    uid, target = int(uid), max(0, int(value))
    async with storage.lock(f"legacy-wallet:{uid}", ttl=10, wait=2.0) as acquired:
        if not acquired: return await _legacy_wallet(uid)
        current = await _legacy_wallet(uid); delta = target - current
        return await storage.incrby(f"wallet:{uid}", delta) if delta else current

async def _ready_probe():
    probe = Storage()
    try: return await health_check(probe)
    finally: await probe.close()

class _HealthHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, object]):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers()
        if self.command != "HEAD": self.wfile.write(body)
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self._send(200, {"status": "ok", "service": "midnight-oracle", "engine": "v2"}); return
        if self.path == "/ready":
            try:
                result = asyncio.run(_ready_probe()); self._send(200 if result.status == "ok" else 503, result.as_dict())
            except Exception:
                log.exception("Readiness probe failed"); self._send(503, {"status": "degraded", "storage": "error", "bot": "unknown", "engine": "v2"})
            return
        self._send(404, {"status": "not_found"})
    def do_HEAD(self): self.do_GET()
    def log_message(self, *_args): return

def _start_health_server():
    port = int(os.getenv("PORT", "10000")); server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="midnight-health").start(); return server

async def _acquire_polling_lease():
    """Allow exactly one Render instance to call Telegram getUpdates.

    Render intentionally overlaps old and new instances during a deploy. A
    short Redis lease prevents both instances from polling at the same time,
    while allowing the replacement instance to wait for the old one to exit.
    """
    if not storage.configured:
        log.warning("POLLING_LEASE disabled: persistent storage is not configured")
        return None
    token = f"{os.getenv('RENDER_SERVICE_ID', 'local')}:{os.getenv('RENDER_INSTANCE_ID', 'unknown')}:{os.getpid()}:{uuid.uuid4().hex}"
    deadline = time.monotonic() + _POLLING_LEASE_WAIT
    while time.monotonic() < deadline:
        if await storage.setnx(_POLLING_LEASE_KEY, token, ttl=_POLLING_LEASE_TTL):
            log.info("POLLING_LEASE acquired instance=%s ttl=%ss", os.getenv("RENDER_INSTANCE_ID", "unknown"), _POLLING_LEASE_TTL)
            return token
        remaining = max(0, int(deadline - time.monotonic()))
        log.warning("POLLING_LEASE busy; waiting for current Telegram poller (%ss remaining)", remaining)
        await asyncio.sleep(3)
    raise RuntimeError("Timed out waiting for the existing Midnight Telegram poller to release its lease")

async def _release_polling_lease(token: str | None):
    if not token or not storage.configured:
        return
    try:
        await storage.eval(
            "if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
            [_POLLING_LEASE_KEY], [token],
        )
        log.info("POLLING_LEASE released")
    except Exception:
        log.exception("POLLING_LEASE release failed; TTL safety net remains")


def _start_polling_lease_renewal(token: str | None):
    if not token or not storage.configured:
        return None, None
    stop_event = threading.Event()
    def _renew_loop():
        failures = 0
        while not stop_event.wait(30):
            try:
                result = asyncio.run(storage.eval(
                    "if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('expire',KEYS[1],ARGV[2]) else return 0 end",
                    [_POLLING_LEASE_KEY], [token, str(_POLLING_LEASE_TTL)],
                ))
                if int(result or 0) != 1:
                    log.error("POLLING_LEASE lost; terminating this poller to prevent Telegram Conflict")
                    os._exit(75)
                failures = 0
            except Exception:
                failures += 1
                log.exception("POLLING_LEASE renewal failed (%d/3)", failures)
                if failures >= 3:
                    log.error("POLLING_LEASE renewal failed repeatedly; terminating this poller")
                    os._exit(75)
    thread = threading.Thread(target=_renew_loop, daemon=True, name="midnight-polling-lease")
    thread.start()
    return stop_event, thread

legacy_bot.deathgames = deathgames_v2
_legacy_post_init = legacy_bot._post_init

_V2_COMMANDS = [
    BotCommand("cricketduel", "Challenge someone to Midnight Cricket"), BotCommand("midnightplay", "Search and play a song in VC"),
    BotCommand("nowplaying", "Show the current VC track"), BotCommand("stopmusic", "Stop Midnight Radio"), BotCommand("pausemusic", "Pause Midnight Radio"), BotCommand("resumemusic", "Resume Midnight Radio"),
    BotCommand("mprofile", "Open your Midnight identity"), BotCommand("achievements", "View your Midnight marks"), BotCommand("midnightevent", "Open a Midnight world event"), BotCommand("upgradhelp", "Read the V2 upgrade guide"),
    BotCommand("settrigger", "Set Midnight's group wake word"), BotCommand("triggerinfo", "Show the group's Midnight wake word"), BotCommand("grouporacle", "Read Midnight's lightweight room activity"),
    BotCommand("bond", "Let Midnight choose a bond automatically"), BotCommand("signal", "Separate signal from noise in a message"),
]
_PRIVATE_PREFERRED = {"start","help","chat","persona","balance","daily","wallet","deposit","withdraw","setpass","changepass","recover","crush","clearcrush","bestie","afk","remind","id","info","profile","inventory","settings","mprofile","achievements","upgradhelp"}
_ADMIN_PREFERRED = {"ban","kick","mute","unmute","warn","warnings","clearwarns","pin","unpin","purge","setrules","lock","unlock","setwelcome","setgoodbye","invite","cwin","cplay","oraclehour"}

def _dedupe(commands):
    out, seen = [], set()
    for cmd in commands:
        if cmd.command in seen: continue
        seen.add(cmd.command); out.append(cmd)
    return out

def _command_registry(): return _dedupe(list(getattr(legacy_bot, "BOT_COMMANDS", [])) + _V2_COMMANDS)
def _take(commands, names, limit=100): return _dedupe([c for c in commands if c.command in names] + [c for c in commands if c.command not in names])[:limit]

async def _publish_v2_command_menu(application):
    commands = _command_registry(); private_commands = _take(commands, _PRIVATE_PREFERRED); group_commands = commands[:100]; admin_commands = _take(_dedupe(group_commands + [c for c in commands if c.command in _ADMIN_PREFERRED]), _ADMIN_PREFERRED)
    await application.bot.set_my_commands([], scope=BotCommandScopeDefault()); await application.bot.set_my_commands([], scope=BotCommandScopeAllGroupChats()); await application.bot.set_my_commands([], scope=BotCommandScopeAllChatAdministrators())
    await application.bot.set_my_commands(private_commands, scope=BotCommandScopeDefault()); await application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats()); await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    await publish_owner_menu(application)
    log.info("COMMAND_MENU registry=%d private=%d group=%d admin=%d owner_controls=private", len(commands), len(private_commands), len(group_commands), len(admin_commands))

async def _post_init(application):
    try:
        log.info("STARTUP service=midnight-oracle engine=v2 render_service=%s instance=%s", os.getenv("RENDER_SERVICE_ID","unknown"), os.getenv("RENDER_INSTANCE_ID","unknown"))
        await storage.start(); await _legacy_post_init(application); await deathgames_v2.load_from_storage(); recovered = await recover_deathgames(application, legacy_bot)
        install_autonomy(application); install_cricket_v2(application); install_deathgames_v2(application); install_v2_features(application); install_v2_social(application); install_v2_help(application); install_v2_autonomous(application); install_social_intelligence(application); install_bond_signal(application); install_vc_player(application); install_owner_tools(application)
        await vc_player.start(); await _publish_v2_command_menu(application)
        if recovered: log.info("RECOVERY recovered_deathgames=%d", recovered)
        log.info("READY handlers=installed polling=starting")
    except Exception:
        log.exception("STARTUP_FAILED"); raise

legacy_bot.html = html; legacy_bot._generate_gemini = _generate_gemini; legacy_bot._coins = _legacy_coins; legacy_bot._setcoins = _legacy_setcoins; legacy_bot._addcoins = _legacy_addcoins; legacy_bot._wallet = _legacy_wallet; legacy_bot._setwallet = _legacy_setwallet; legacy_bot._start_dummy_server = _start_health_server; legacy_bot._post_init = _post_init; legacy_bot.chat.generate_reply = core_generate_reply; legacy_bot.utility.set_afk = core_set_afk; legacy_bot.utility.check_afk_mentions = core_check_afk_mentions

if __name__ == "__main__":
    log.info("PROCESS starting pid=%s python=%s", os.getpid(), os.sys.version.split()[0])
    lease_token = asyncio.run(_acquire_polling_lease())
    renew_stop = renew_thread = None
    try:
        renew_stop, renew_thread = _start_polling_lease_renewal(lease_token)
        legacy_bot.main()
    finally:
        if renew_stop is not None:
            renew_stop.set()
        asyncio.run(_release_polling_lease(lease_token))
