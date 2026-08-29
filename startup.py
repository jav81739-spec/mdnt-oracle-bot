"""Midnight Oracle runtime: single-instance polling, health, registry and shutdown."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger("midnight.startup")

_LEASE_KEY = "midnight:polling_lease"
_LEASE_TTL = 60
_LEASE_REFRESH = 20
_LEASE_WAIT_MAX = 90
_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"
_REGISTRY_KEY = "midnight:chat_registry"
_LEASE_TOKEN = f"{_INSTANCE_ID}:{time.time_ns()}"

_storage = None
_app = None
_lease_task = None
_health_server = None
_shutting_down = False
_ready = False


def init(storage_client=None):
    global _storage
    _storage = storage_client


async def _store_get(key):
    if _storage is None:
        return None
    try:
        value = _storage.get(key)
        return await value if asyncio.iscoroutine(value) else value
    except Exception as exc:
        log.warning("storage GET failed | key=%s | %s", key, exc)
        return None


async def _store_set(key, value, ttl=0):
    if _storage is None:
        return False
    try:
        result = _storage.setex(key, ttl, value) if ttl else _storage.set(key, value)
        if asyncio.iscoroutine(result):
            result = await result
        return bool(result)
    except Exception as exc:
        log.warning("storage SET failed | key=%s | %s", key, exc)
        return False


async def _store_setnx(key, value, ttl):
    if _storage is None:
        return False
    try:
        result = _storage.setnx(key, value, ttl=ttl)
        if asyncio.iscoroutine(result):
            result = await result
        return bool(result)
    except Exception as exc:
        log.warning("storage SETNX failed | key=%s | %s", key, exc)
        return False


async def _store_delete(key):
    if _storage is None:
        return False
    try:
        result = _storage.delete(key)
        if asyncio.iscoroutine(result):
            result = await result
        return bool(result)
    except Exception as exc:
        log.warning("storage DELETE failed | key=%s | %s", key, exc)
        return False


async def _acquire_lease():
    """Atomically acquire the polling lease; never use GET→SET ownership."""
    if await _store_setnx(_LEASE_KEY, _LEASE_TOKEN, _LEASE_TTL):
        log.info("Polling lease acquired | instance=%s", _INSTANCE_ID)
        return True
    log.info("POLLING_LEASE busy | another instance owns Telegram polling")
    return False


async def _refresh_lease():
    if _storage is None:
        return False
    script = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('SET',KEYS[1],ARGV[1],'EX',ARGV[2]) else return 0 end"
    try:
        if hasattr(_storage, "eval"):
            result = _storage.eval(script, [_LEASE_KEY], [_LEASE_TOKEN, str(_LEASE_TTL)])
            if asyncio.iscoroutine(result):
                result = await result
            ok = str(result).upper() in {"OK", "TRUE", "1"}
        else:
            current = await _store_get(_LEASE_KEY)
            ok = current == _LEASE_TOKEN and await _store_set(_LEASE_KEY, _LEASE_TOKEN, _LEASE_TTL)
        if not ok:
            log.error("Polling lease ownership lost")
        return ok
    except Exception as exc:
        log.warning("Lease refresh failed: %s", exc)
        return False


async def _release_lease():
    if _storage is None:
        return
    script = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"
    try:
        if hasattr(_storage, "eval"):
            result = _storage.eval(script, [_LEASE_KEY], [_LEASE_TOKEN])
            if asyncio.iscoroutine(result):
                await result
        elif await _store_get(_LEASE_KEY) == _LEASE_TOKEN:
            await _store_delete(_LEASE_KEY)
        log.info("Polling lease released | instance=%s", _INSTANCE_ID)
    except Exception as exc:
        log.warning("Lease release failed: %s", exc)


async def _lease_heartbeat_loop():
    while not _shutting_down:
        await asyncio.sleep(_LEASE_REFRESH)
        if _shutting_down:
            return
        if not await _refresh_lease():
            log.critical("Polling lease lost — shutting down to prevent Telegram polling conflict")
            await _graceful_shutdown()
            return


async def _wait_for_lease():
    deadline = time.monotonic() + _LEASE_WAIT_MAX
    while time.monotonic() < deadline:
        if await _acquire_lease():
            return True
        remaining = deadline - time.monotonic()
        await asyncio.sleep(min(5, max(0.5, remaining)))
    log.warning("POLLING_LEASE still busy after %ds; final atomic attempt", _LEASE_WAIT_MAX)
    return await _acquire_lease()


async def register_chat(chat_id: int, chat_type: str, title: str = ""):
    if chat_type == "private":
        return
    try:
        raw = await _store_get(_REGISTRY_KEY)
        registry = json.loads(raw) if raw else {}
        registry[str(chat_id)] = {"type": chat_type, "title": (title or "")[:100], "seen": int(time.time())}
        await _store_set(_REGISTRY_KEY, json.dumps(registry, ensure_ascii=False))
    except Exception as exc:
        log.warning("register_chat failed | chat=%s | %s", chat_id, exc)


async def get_chat_registry():
    try:
        raw = await _store_get(_REGISTRY_KEY)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


async def get_broadcast_targets(include_groups=True, include_channels=True):
    registry = await get_chat_registry()
    targets = []
    for cid, info in registry.items():
        kind = info.get("type", "")
        if include_groups and kind in ("group", "supergroup"):
            targets.append(int(cid))
        elif include_channels and kind == "channel":
            targets.append(int(cid))
    return targets


class _HealthHandler(BaseHTTPRequestHandler):
    def _respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self._respond(200, json.dumps({"status": "ok" if not _shutting_down else "shutting_down", "ready": _ready, "instance": _INSTANCE_ID}).encode())
        elif self.path == "/ready":
            ready = _ready and not _shutting_down
            self._respond(200 if ready else 503, json.dumps({"ready": ready}).encode())
        else:
            self._respond(404, b'{"status":"not_found"}')

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, *_):
        return


class _ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True


def start_health_server():
    global _health_server
    port = int(os.getenv("PORT", "10000"))
    _health_server = _ReuseHTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=_health_server.serve_forever, daemon=True, name="midnight-health").start()
    log.info("Health server listening on 0.0.0.0:%d", port)
    return _health_server


def _install_signal_handlers(loop):
    def handler(signum, _frame):
        log.info("Received %s — initiating graceful shutdown", signal.Signals(signum).name)
        loop.call_soon_threadsafe(lambda: asyncio.create_task(_graceful_shutdown()))
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


async def _graceful_shutdown():
    global _shutting_down, _ready
    if _shutting_down:
        return
    _shutting_down = True
    _ready = False
    log.info("Graceful shutdown started")
    if _lease_task and not _lease_task.done():
        _lease_task.cancel()
        try:
            await _lease_task
        except asyncio.CancelledError:
            pass
    if _app is not None:
        try:
            if _app.updater.running:
                await _app.updater.stop()
            if _app.running:
                await _app.stop()
            await _app.shutdown()
            log.info("Telegram application stopped")
        except Exception as exc:
            log.warning("Error stopping Telegram app: %s", exc)
    await _release_lease()
    if _health_server:
        threading.Thread(target=_health_server.shutdown, daemon=True).start()
    log.info("Graceful shutdown complete")


async def run(application, storage_client=None):
    global _storage, _app, _lease_task, _ready
    _storage = storage_client
    _app = application
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)
    start_health_server()
    if not await _wait_for_lease():
        log.critical("Cannot start: polling lease unavailable")
        return
    _lease_task = asyncio.create_task(_lease_heartbeat_loop(), name="polling_lease_heartbeat")
    log.info("Starting Telegram polling — instance %s", _INSTANCE_ID)
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "edited_message", "callback_query", "chat_member", "my_chat_member", "channel_post"],
        )
        _ready = True
        log.info("Telegram polling active | ready=true")
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("Fatal error in polling loop")
    finally:
        await _graceful_shutdown()
