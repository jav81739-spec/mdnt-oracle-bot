"""Midnight Oracle production entrypoint."""
from __future__ import annotations

import atexit
import asyncio
import hashlib
import html
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import legacy_bot
from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators,
)
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
from handlers import deathgames_v2

log = logging.getLogger("midnight.entrypoint")

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

# ---------------------------------------------------------------------------
# Telegram polling singleton guard.
# Render can briefly overlap old/new processes during a deploy. Telegram only
# permits one getUpdates consumer per bot token, so use the shared Redis store
# to elect exactly one polling owner. This guard is independent of bot logic.
# ---------------------------------------------------------------------------
_SINGLETON_KEY = "midnight:v2:telegram-poller"
_SINGLETON_TTL = 120
_SINGLETON_TOKEN = hashlib.sha256((os.getenv("BOT_TOKEN") or "").encode()).hexdigest()[:24]
_singleton_owner = f"{os.getenv('RENDER_INSTANCE_ID') or os.getenv('RENDER_SERVICE_ID') or os.getpid()}:{time.time_ns()}"
_singleton_redis = None
_singleton_stop = threading.Event()
_singleton_heartbeat = None


def _singleton_client():
    global _singleton_redis
    if _singleton_redis is not None:
        return _singleton_redis
    try:
        import redis
        url = os.getenv("REDIS_URL") or os.getenv("KV_URL") or os.getenv("UPSTASH_REDIS_REST_URL") or ""
        password = os.getenv("REDIS_PASSWORD") or os.getenv("UPSTASH_REDIS_REST_TOKEN") or ""
        if url.startswith("redis://") or url.startswith("rediss://"):
            _singleton_redis = redis.Redis.from_url(url, decode_responses=True, socket_timeout=3)
        elif url.startswith("https://"):
            host = url[len("https://"):].rstrip("/")
            _singleton_redis = redis.Redis(host=host, port=6379, password=password, ssl=True, decode_responses=True, socket_timeout=3)
        else:
            _singleton_redis = redis.Redis(host="localhost", port=6379, decode_responses=True, socket_timeout=3)
        return _singleton_redis
    except Exception as exc:
        log.warning("Singleton guard unavailable: %s", exc)
        return None


def _acquire_singleton() -> bool:
    client = _singleton_client()
    if client is None:
        # Do not silently create a false sense of safety when Redis is absent.
        # Render should still run one instance; the log makes the limitation explicit.
        log.warning("Telegram singleton guard is unavailable; relying on deployment single-instance configuration")
        return True
    try:
        acquired = bool(client.set(f"{_SINGLETON_KEY}:{_SINGLETON_TOKEN}", _singleton_owner, nx=True, ex=_SINGLETON_TTL))
        if acquired:
            log.info("Telegram polling singleton acquired")
        else:
            current = client.get(f"{_SINGLETON_KEY}:{_SINGLETON_TOKEN}")
            log.error("Telegram polling singleton already owned by another instance (%s); refusing to start a second poller", current or "unknown")
        return acquired
    except Exception as exc:
        log.warning("Singleton acquire failed: %s; relying on deployment single-instance configuration", exc)
        return True


def _renew_singleton():
    client = _singleton_client()
    key = f"{_SINGLETON_KEY}:{_SINGLETON_TOKEN}"
    while not _singleton_stop.wait(30):
        if client is None:
            continue
        try:
            if client.get(key) != _singleton_owner:
                log.error("Telegram polling singleton ownership was lost; stopping this process")
                _singleton_stop.set()
                return
            client.expire(key, _SINGLETON_TTL)
        except Exception as exc:
            log.warning("Singleton heartbeat failed: %s", exc)


def _release_singleton():
    _singleton_stop.set()
    client = _singleton_client()
    if client is None:
        return
    key = f"{_SINGLETON_KEY}:{_SINGLETON_TOKEN}"
    try:
        if client.get(key) == _singleton_owner:
            client.delete(key)
    except Exception:
        pass


def _start_singleton_guard() -> bool:
    global _singleton_heartbeat
    if not _acquire_singleton():
        return False
    atexit.register(_release_singleton)
    _singleton_heartbeat = threading.Thread(target=_renew_singleton, daemon=True, name="midnight-poller-guard")
    _singleton_heartbeat.start()
    return True

legacy_bot.deathgames = deathgames_v2
_legacy_post_init = legacy_bot._post_init

_V2_COMMANDS = [
    BotCommand("cricketduel", "Challenge someone to Midnight Cricket"),
    BotCommand("midnightplay", "Search and play a song in VC"),
    BotCommand("nowplaying", "Show the current VC track"),
    BotCommand("stopmusic", "Stop Midnight Radio"),
    BotCommand("pausemusic", "Pause Midnight Radio"),
    BotCommand("resumemusic", "Resume Midnight Radio"),
    BotCommand("mprofile", "Open your Midnight identity"),
    BotCommand("achievements", "View your Midnight marks"),
    BotCommand("midnightevent", "Open a Midnight world event"),
    BotCommand("upgradhelp", "Read the V2 upgrade guide"),
    BotCommand("settrigger", "Set Midnight's group wake word"),
    BotCommand("triggerinfo", "Show the group's Midnight wake word"),
    BotCommand("grouporacle", "Read Midnight's lightweight room activity"),
    BotCommand("bond", "Let Midnight choose a bond automatically"),
    BotCommand("signal", "Separate signal from noise in a message"),
]

_PRIVATE_PREFERRED = {
    "start", "help", "chat", "persona", "balance", "daily", "wallet", "deposit",
    "withdraw", "setpass", "changepass", "recover", "crush", "clearcrush", "bestie",
    "afk", "remind", "id", "info", "profile", "inventory", "settings", "mprofile",
    "achievements", "upgradhelp",
}

_ADMIN_PREFERRED = {
    "ban", "kick", "mute", "unmute", "warn", "warnings", "clearwarns", "pin", "unpin",
    "purge", "setrules", "lock", "unlock", "setwelcome", "setgoodbye", "invite",
    "cwin", "cplay", "oraclehour", "broadcast", "announce",
}

def _dedupe(commands):
    out = []
    seen = set()
    for cmd in commands:
        name = cmd.command
        if name in seen: continue
        seen.add(name); out.append(cmd)
    return out

def _command_registry():
    return _dedupe(list(getattr(legacy_bot, "BOT_COMMANDS", [])) + _V2_COMMANDS)

def _take(commands, names, limit=100):
    preferred = [c for c in commands if c.command in names]
    rest = [c for c in commands if c.command not in names]
    return _dedupe(preferred + rest)[:limit]

async def _publish_v2_command_menu(application):
    """Publish deterministic, scoped menus without stale/default collisions."""
    commands = _command_registry()
    private_commands = _take(commands, _PRIVATE_PREFERRED)
    group_commands = commands[:100]
    admin_commands = _take(_dedupe(group_commands + [c for c in commands if c.command in _ADMIN_PREFERRED]), _ADMIN_PREFERRED)
    await application.bot.set_my_commands([], scope=BotCommandScopeDefault())
    await application.bot.set_my_commands([], scope=BotCommandScopeAllGroupChats())
    await application.bot.set_my_commands([], scope=BotCommandScopeAllChatAdministrators())
    await application.bot.set_my_commands(private_commands, scope=BotCommandScopeDefault())
    await application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
    await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    log.info("Command menus published: registry=%d private=%d group=%d admin=%d", len(commands), len(private_commands), len(group_commands), len(admin_commands))

async def _post_init(application):
    try:
        await storage.start(); await _legacy_post_init(application)
        await deathgames_v2.load_from_storage(); recovered = await recover_deathgames(application, legacy_bot)
        install_autonomy(application); install_cricket_v2(application); install_deathgames_v2(application)
        install_v2_features(application); install_v2_social(application); install_v2_help(application); install_v2_autonomous(application)
        install_social_intelligence(application); install_bond_signal(application)
        install_vc_player(application)
        await vc_player.start(); await _publish_v2_command_menu(application)
        if recovered: log.info("Recovered %d death-game record(s)", recovered)
        log.info("Midnight V2 autonomous, cricket, social-intelligence, bond/signal, death-game, help and VC layers online")
    except Exception:
        log.exception("Startup initialization/recovery failed"); raise

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
    if not _start_singleton_guard():
        raise SystemExit(0)
    legacy_bot.main()
