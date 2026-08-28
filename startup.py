"""
startup.py — Midnight Oracle canonical startup manager.

Fixes every P0 architectural problem:
  ✅ Single entrypoint — import this from bot.py, nothing else
  ✅ Polling ownership — only one instance ever polls Telegram
  ✅ Stale lease recovery — expired leases auto-released
  ✅ Clean async lifecycle — no asyncio.run() inside threads
  ✅ Graceful SIGTERM — releases lease before exit
  ✅ Health server — isolated from bot async lifecycle
  ✅ Chat registry — auto-discovers groups/channels on every update
"""

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
from typing import Optional

log = logging.getLogger("midnight.startup")

_LEASE_KEY = "midnight:polling_lease"
_LEASE_TTL = 60
_LEASE_REFRESH = 20
_LEASE_WAIT_MAX = 90
_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"

_storage = None
_app = None
_lease_task: Optional[asyncio.Task] = None
_health_server: Optional[HTTPServer] = None
_shutting_down = False

async def _store_get(key: str) -> Optional[str]:
    try:
        if _storage is None:
            return None
        result = _storage.get(key)
        if asyncio.iscoroutine(result):
            result = await result
        return result
    except Exception as exc:
        log.debug("storage.get(%s) failed: %s", key, exc)
        return None

async def _store_set(key: str, value: str, ttl: int = 0) -> bool:
    try:
        if _storage is None:
            return False
        result = _storage.setex(key, ttl, value) if ttl else _storage.set(key, value)
        if asyncio.iscoroutine(result):
            await result
        return True
    except Exception as exc:
        log.debug("storage.set(%s) failed: %s", key, exc)
        return False

async def _store_delete(key: str) -> bool:
    try:
        if _storage is None:
            return False
        result = _storage.delete(key)
        if asyncio.iscoroutine(result):
            await result
        return True
    except Exception as exc:
        log.debug("storage.delete(%s) failed: %s", key, exc)
        return False

async def _acquire_lease() -> bool:
    raw = await _store_get(_LEASE_KEY)
    if raw:
        try:
            info = json.loads(raw)
            owner = info.get("instance")
            ts = info.get("ts", 0)
            age = time.time() - ts
            if owner == _INSTANCE_ID:
                await _refresh_lease()
                return True
            if age < _LEASE_TTL:
                log.info("POLLING_LEASE held by %s (age %.0fs, TTL %ds)", owner, age, _LEASE_TTL)
                return False
            log.warning("Stale lease from %s (age %.0fs > TTL %ds) — reclaiming", owner, age, _LEASE_TTL)
        except Exception:
            pass

    payload = json.dumps({"instance": _INSTANCE_ID, "ts": time.time()})
    ok = await _store_set(_LEASE_KEY, payload, ttl=_LEASE_TTL)
    if ok:
        log.info("Polling lease acquired by %s", _INSTANCE_ID)
    return ok

async def _refresh_lease():
    payload = json.dumps({"instance": _INSTANCE_ID, "ts": time.time()})
    await _store_set(_LEASE_KEY, payload, ttl=_LEASE_TTL)

async def _release_lease():
    raw = await _store_get(_LEASE_KEY)
    if raw:
        try:
            info = json.loads(raw)
            if info.get("instance") == _INSTANCE_ID:
                await _store_delete(_LEASE_KEY)
                log.info("Polling lease released by %s", _INSTANCE_ID)
                return
        except Exception:
            pass
    log.debug("Lease not owned by us — skipping release")

async def _lease_heartbeat_loop():
    while not _shutting_down:
        await asyncio.sleep(_LEASE_REFRESH)
        if _shutting_down:
            break
        try:
            await _refresh_lease()
        except Exception as exc:
            log.warning("Lease refresh failed: %s", exc)

async def _wait_for_lease() -> bool:
    deadline = time.time() + _LEASE_WAIT_MAX
    while time.time() < deadline:
        if await _acquire_lease():
            return True
        remaining = deadline - time.time()
        wait = min(5, remaining)
        if wait <= 0:
            break
        log.info("POLLING_LEASE busy — waiting %.0fs (%.0fs remaining)", wait, remaining)
        await asyncio.sleep(wait)
    log.error("Could not acquire polling lease within %ds — giving up", _LEASE_WAIT_MAX)
    return False

_REGISTRY_KEY = "midnight:chat_registry"

async def register_chat(chat_id: int, chat_type: str, title: str = ""):
    if chat_type == "private":
        return
    try:
        raw = await _store_get(_REGISTRY_KEY)
        registry: dict = json.loads(raw) if raw else {}
        registry[str(chat_id)] = {"type": chat_type, "title": title[:100], "seen": int(time.time())}
        await _store_set(_REGISTRY_KEY, json.dumps(registry, ensure_ascii=False))
    except Exception as exc:
        log.debug("register_chat failed: %s", exc)

async def get_chat_registry() -> dict:
    try:
        raw = await _store_get(_REGISTRY_KEY)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}

async def get_broadcast_targets(include_groups: bool = True, include_channels: bool = True) -> list[int]:
    registry = await get_chat_registry()
    targets = []
    for cid_str, info in registry.items():
        t = info.get("type", "")
        if include_groups and t in ("group", "supergroup"):
            targets.append(int(cid_str))
        elif include_channels and t == "channel":
            targets.append(int(cid_str))
    return targets

class _HealthHandler(BaseHTTPRequestHandler):
    def _respond(self, status: int, body: bytes, ctype: str = "text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            status = "shutting_down" if _shutting_down else "ok"
            code = 503 if _shutting_down else 200
            self._respond(code, json.dumps({"status": status, "instance": _INSTANCE_ID}).encode(), "application/json")
        elif self.path == "/ready":
            ready = (_app is not None) and (not _shutting_down)
            self._respond(200 if ready else 503, json.dumps({"ready": ready}).encode(), "application/json")
        else:
            self._respond(404, b'{"status":"not_found"}', "application/json")

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, *_):
        return

class _ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True

def start_health_server() -> HTTPServer:
    global _health_server
    port = int(os.getenv("PORT", "10000"))
    _health_server = _ReuseHTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(target=_health_server.serve_forever, daemon=True, name="midnight-health")
    t.start()
    log.info("Health server listening on 0.0.0.0:%d", port)
    return _health_server

def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    def _handle_signal(signum, _frame):
        name = signal.Signals(signum).name
        log.info("Received %s — initiating graceful shutdown", name)
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_graceful_shutdown(), loop=loop))
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

async def _graceful_shutdown():
    """Stop the bot and release resources without stopping the loop itself.

    asyncio.run() owns this event loop. Calling loop.stop() from inside this
    coroutine makes asyncio.run() raise 'Event loop stopped before Future
    completed'. Let the coroutine return normally so asyncio.run() can close
    the loop cleanly.
    """
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    log.info("Graceful shutdown started")

    if _lease_task and not _lease_task.done():
        _lease_task.cancel()
        try:
            await _lease_task
        except asyncio.CancelledError:
            pass

    if _app is not None:
        try:
            if _app.updater and _app.updater.running:
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
    global _storage, _app, _lease_task

    if not logging.root.handlers:
        logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)

    _storage = storage_client
    _app = application
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)
    start_health_server()

    if not await _wait_for_lease():
        log.critical("Cannot start: polling lease unavailable. Exiting.")
        return

    _lease_task = asyncio.ensure_future(_lease_heartbeat_loop())
    log.info("Starting Telegram polling — instance %s", _INSTANCE_ID)

    try:
        await application.initialize()
        if application.post_init is not None:
            await application.post_init(application)
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "edited_message", "callback_query", "chat_member", "my_chat_member"],
        )
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.exception("Fatal error in polling loop: %s", exc)
    finally:
        await _graceful_shutdown()

def init(storage_client=None):
    global _storage
    _storage = storage_client
