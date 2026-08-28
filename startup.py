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

# ── Lease constants ────────────────────────────────────────────────────────────
_LEASE_KEY        = "midnight:polling_lease"
_LEASE_TTL        = 60          # seconds — lease expires if not refreshed
_LEASE_REFRESH    = 20          # seconds — how often to heartbeat
_LEASE_WAIT_MAX   = 90          # seconds — how long to wait for stale lease
_INSTANCE_ID      = f"{socket.gethostname()}:{os.getpid()}"

# ── Module-level state ─────────────────────────────────────────────────────────
_storage          = None        # set by init()
_app              = None        # PTB Application
_lease_task: Optional[asyncio.Task] = None
_health_server: Optional[HTTPServer] = None
_shutting_down    = False


# ══════════════════════════════════════════════════════════════════════════════
# STORAGE helpers (thin wrapper — works with core.storage OR upstash-redis)
# ══════════════════════════════════════════════════════════════════════════════

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
        if ttl:
            result = _storage.setex(key, ttl, value)
        else:
            result = _storage.set(key, value)
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


# ══════════════════════════════════════════════════════════════════════════════
# POLLING LEASE — only one Midnight polls Telegram at a time
# ══════════════════════════════════════════════════════════════════════════════

async def _acquire_lease() -> bool:
    """Try to acquire the polling lease. Returns True if we own it."""
    raw = await _store_get(_LEASE_KEY)
    if raw:
        try:
            info = json.loads(raw)
            owner = info.get("instance")
            ts    = info.get("ts", 0)
            age   = time.time() - ts
            if owner == _INSTANCE_ID:
                # We already own it — refresh and continue
                await _refresh_lease()
                return True
            if age < _LEASE_TTL:
                log.info(
                    "POLLING_LEASE held by %s (age %.0fs, TTL %ds)",
                    owner, age, _LEASE_TTL,
                )
                return False
            # Stale lease — previous instance died without releasing
            log.warning(
                "Stale lease from %s (age %.0fs > TTL %ds) — reclaiming",
                owner, age, _LEASE_TTL,
            )
        except Exception:
            pass  # corrupt entry — overwrite it

    payload = json.dumps({"instance": _INSTANCE_ID, "ts": time.time()})
    ok = await _store_set(_LEASE_KEY, payload, ttl=_LEASE_TTL)
    if ok:
        log.info("Polling lease acquired by %s", _INSTANCE_ID)
    return ok


async def _refresh_lease():
    """Heartbeat — called every _LEASE_REFRESH seconds."""
    payload = json.dumps({"instance": _INSTANCE_ID, "ts": time.time()})
    await _store_set(_LEASE_KEY, payload, ttl=_LEASE_TTL)


async def _release_lease():
    """Release lease on clean shutdown."""
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
    """Background task: keep refreshing the lease while we own it."""
    while not _shutting_down:
        await asyncio.sleep(_LEASE_REFRESH)
        if _shutting_down:
            break
        try:
            await _refresh_lease()
        except Exception as exc:
            log.warning("Lease refresh failed: %s", exc)


async def _wait_for_lease() -> bool:
    """
    Wait up to _LEASE_WAIT_MAX seconds for the lease to become available.
    Returns True if acquired, False if timeout.
    """
    deadline = time.time() + _LEASE_WAIT_MAX
    while time.time() < deadline:
        if await _acquire_lease():
            return True
        remaining = deadline - time.time()
        wait = min(5, remaining)
        if wait <= 0:
            break
        log.info(
            "POLLING_LEASE busy — waiting %.0fs (%.0fs remaining)",
            wait, remaining,
        )
        await asyncio.sleep(wait)
    log.error("Could not acquire polling lease within %ds — giving up", _LEASE_WAIT_MAX)
    return False


# ══════════════════════════════════════════════════════════════════════════════
# CHAT REGISTRY — auto-discovers groups and channels from incoming updates
# ══════════════════════════════════════════════════════════════════════════════

_REGISTRY_KEY = "midnight:chat_registry"


async def register_chat(chat_id: int, chat_type: str, title: str = ""):
    """
    Called from update handler to track every group/channel the bot is in.
    Chat type: 'group', 'supergroup', 'channel', 'private'
    """
    if chat_type == "private":
        return  # Don't store private chats in the broadcast registry
    try:
        raw = await _store_get(_REGISTRY_KEY)
        registry: dict = json.loads(raw) if raw else {}
        registry[str(chat_id)] = {
            "type":  chat_type,
            "title": title[:100],
            "seen":  int(time.time()),
        }
        await _store_set(_REGISTRY_KEY, json.dumps(registry, ensure_ascii=False))
    except Exception as exc:
        log.debug("register_chat failed: %s", exc)


async def get_chat_registry() -> dict:
    """Returns {chat_id_str: {type, title, seen}} for all known chats."""
    try:
        raw = await _store_get(_REGISTRY_KEY)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


async def get_broadcast_targets(
    include_groups: bool = True,
    include_channels: bool = True,
) -> list[int]:
    """Return list of chat IDs eligible for broadcast."""
    registry = await get_chat_registry()
    targets = []
    for cid_str, info in registry.items():
        t = info.get("type", "")
        if include_groups and t in ("group", "supergroup"):
            targets.append(int(cid_str))
        elif include_channels and t == "channel":
            targets.append(int(cid_str))
    return targets


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH SERVER — isolated from bot async lifecycle (runs in own thread)
# ══════════════════════════════════════════════════════════════════════════════

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
            body = json.dumps(
                {"status": status, "instance": _INSTANCE_ID}
            ).encode()
            self._respond(code, body, "application/json")
        elif self.path == "/ready":
            ready = (_app is not None) and (not _shutting_down)
            code = 200 if ready else 503
            body = json.dumps({"ready": ready}).encode()
            self._respond(code, body, "application/json")
        else:
            self._respond(404, b'{"status":"not_found"}', "application/json")

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, *_):
        return


class _ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True


def start_health_server() -> HTTPServer:
    """Start the health HTTP server in a daemon thread. Call once at startup."""
    global _health_server
    port = int(os.getenv("PORT", "10000"))
    _health_server = _ReuseHTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(
        target=_health_server.serve_forever,
        daemon=True,
        name="midnight-health",
    )
    t.start()
    log.info("Health server listening on 0.0.0.0:%d", port)
    return _health_server


# ══════════════════════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN — releases lease, stops polling, closes cleanly
# ══════════════════════════════════════════════════════════════════════════════

def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    """Install SIGTERM/SIGINT handlers that trigger graceful shutdown."""
    def _handle_signal(signum, _frame):
        name = signal.Signals(signum).name
        log.info("Received %s — initiating graceful shutdown", name)
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(_graceful_shutdown(), loop=loop)
        )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


async def _graceful_shutdown():
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    log.info("Graceful shutdown started")

    # 1. Cancel lease heartbeat
    if _lease_task and not _lease_task.done():
        _lease_task.cancel()
        try:
            await _lease_task
        except asyncio.CancelledError:
            pass

    # 2. Stop Telegram polling
    if _app is not None:
        try:
            await _app.updater.stop()
            await _app.stop()
            await _app.shutdown()
            log.info("Telegram application stopped")
        except Exception as exc:
            log.warning("Error stopping Telegram app: %s", exc)

    # 3. Release polling lease
    await _release_lease()

    # 4. Stop health server
    if _health_server:
        threading.Thread(
            target=_health_server.shutdown, daemon=True
        ).start()

    log.info("Graceful shutdown complete")

    # 5. Stop the event loop
    loop = asyncio.get_event_loop()
    loop.stop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def run(application, storage_client=None):
    """
    Main coroutine. Call this from bot.py:

        import asyncio
        from startup import run
        asyncio.run(run(application, storage_client=redis_compat))

    Parameters
    ----------
    application : telegram.ext.Application
        Fully built PTB Application (handlers already added).
    storage_client : optional
        Any object with .get / .set / .setex / .delete methods.
        Pass your RedisCompat / upstash client here.
    """
    global _storage, _app, _lease_task

    # Configure logging if not already done
    if not logging.root.handlers:
        logging.basicConfig(
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            level=logging.INFO,
        )

    _storage = storage_client
    _app = application

    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)

    # Start health server (isolated thread — no async involvement)
    start_health_server()

    # Acquire polling lease (wait if another instance is shutting down)
    if not await _wait_for_lease():
        log.critical("Cannot start: polling lease unavailable. Exiting.")
        return

    # Start lease heartbeat
    _lease_task = asyncio.ensure_future(_lease_heartbeat_loop())

    log.info("Starting Telegram polling — instance %s", _INSTANCE_ID)

    try:
        await application.initialize()
        if application.post_init is not None:
            await application.post_init(application)
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "edited_message", "callback_query",
                             "chat_member", "my_chat_member"],
        )
        # Run until shutdown signal
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.exception("Fatal error in polling loop: %s", exc)
    finally:
        await _graceful_shutdown()


def init(storage_client=None):
    """
    Synchronous wrapper — sets storage client without starting the bot.
    Useful for testing or partial initialization.
    """
    global _storage
    _storage = storage_client
