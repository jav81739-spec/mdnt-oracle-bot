"""Canonical Midnight Oracle startup manager."""
from __future__ import annotations
import asyncio,json,logging,os,signal,socket,threading,time
from typing import Optional
from http.server import BaseHTTPRequestHandler,HTTPServer
log=logging.getLogger("midnight.startup")
_LEASE_KEY="midnight:polling_lease";_LEASE_TTL=60;_LEASE_REFRESH=20;_LEASE_WAIT_MAX=90;_INSTANCE_ID=f"{socket.gethostname()}:{os.getpid()}";_storage=None;_app=None;_lease_task:Optional[asyncio.Task]=None;_health_server:Optional[HTTPServer]=None;_shutting_down=False
async def _store_get(key):
    try:
        if _storage is None:return None
        result=_storage.get(key);return await result if asyncio.iscoroutine(result) else result
    except Exception:return None
async def _store_set(key,value,ttl=0):
    try:
        if _storage is None:return False
        result=_storage.setex(key,ttl,value) if ttl else _storage.set(key,value)
        return bool(await result if asyncio.iscoroutine(result) else result)
    except Exception:return False
async def _store_setnx(key,value,ttl):
    try:
        if _storage is None:return False
        method=getattr(_storage,"setnx",None)
        if method is not None:
            result=method(key,value,ttl);return bool(await result if asyncio.iscoroutine(result) else result)
        return False
    except Exception:return False
async def _store_delete(key):
    try:
        if _storage is None:return False
        result=_storage.delete(key);return bool(await result if asyncio.iscoroutine(result) else result)
    except Exception:return False
async def _refresh_lease():await _store_set(_LEASE_KEY,json.dumps({"instance":_INSTANCE_ID,"ts":time.time()}),_LEASE_TTL)
async def _acquire_lease():
    raw=await _store_get(_LEASE_KEY)
    if raw:
        try:
            info=json.loads(raw);owner=info.get("instance");age=time.time()-info.get("ts",0)
            if owner==_INSTANCE_ID:await _refresh_lease();return True
            if age<_LEASE_TTL:return False
        except Exception:pass
    return await _store_setnx(_LEASE_KEY,json.dumps({"instance":_INSTANCE_ID,"ts":time.time()}),_LEASE_TTL)
async def _release_lease():
    raw=await _store_get(_LEASE_KEY)
    try:
        if raw and json.loads(raw).get("instance")==_INSTANCE_ID:await _store_delete(_LEASE_KEY)
    except Exception:pass
async def _lease_heartbeat_loop():
    while not _shutting_down:
        await asyncio.sleep(_LEASE_REFRESH)
        if not _shutting_down:await _refresh_lease()
_REGISTRY_KEY="midnight:chat_registry"
async def register_chat(chat_id,chat_type,title=""):
    if chat_type=="private":return
    try:
        raw=await _store_get(_REGISTRY_KEY);registry=json.loads(raw) if raw else {};registry[str(chat_id)]={"type":chat_type,"title":title[:100],"seen":int(time.time())};await _store_set(_REGISTRY_KEY,json.dumps(registry,ensure_ascii=False))
    except Exception:pass
async def get_chat_registry():
    try:
        raw=await _store_get(_REGISTRY_KEY);return json.loads(raw) if raw else {}
    except Exception:return {}
async def get_broadcast_targets(include_groups=True,include_channels=True):
    registry=await get_chat_registry();return [int(cid) for cid,info in registry.items() if (include_groups and info.get("type") in ("group","supergroup")) or (include_channels and info.get("type")=="channel")]
class _HealthHandler(BaseHTTPRequestHandler):
    def _respond(self,status,body,ctype="text/plain"):
        self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(body)));self.end_headers()
        if self.command!="HEAD":self.wfile.write(body)
    def do_GET(self):
        if self.path in ("/","/health","/healthz"):
            self._respond(503 if _shutting_down else 200,json.dumps({"status":"shutting_down" if _shutting_down else "ok","instance":_INSTANCE_ID}).encode(),"application/json")
        elif self.path=="/ready":self._respond(200 if _app and not _shutting_down else 503,json.dumps({"ready":bool(_app and not _shutting_down)}).encode(),"application/json")
        else:self._respond(404,b'{"status":"not_found"}',"application/json")
    do_HEAD=do_GET
    def log_message(self,*_):pass
class _ReuseHTTPServer(HTTPServer):allow_reuse_address=True
def start_health_server():
    global _health_server
    if _health_server is not None:return _health_server
    port=int(os.getenv("PORT","10000"));_health_server=_ReuseHTTPServer(("0.0.0.0",port),_HealthHandler);threading.Thread(target=_health_server.serve_forever,daemon=True).start();return _health_server
def _install_signal_handlers(loop):
    def handler(signum,_frame):loop.call_soon_threadsafe(lambda:asyncio.ensure_future(_graceful_shutdown(),loop=loop))
    signal.signal(signal.SIGTERM,handler);signal.signal(signal.SIGINT,handler)
def _install_jobqueue_compat():
    try:
        from telegram.ext import JobQueue
        if not hasattr(JobQueue,"run_weekly"):
            JobQueue.run_weekly=lambda self,callback,time,weekday=0,**kw:self.run_daily(callback,time=time,days=((int(weekday)+1)%7,),**kw)
    except Exception:pass
async def _verify_command_menu(application):
    try:
        from telegram import BotCommandScopeAllPrivateChats,BotCommandScopeAllGroupChats
        for scope in (BotCommandScopeAllPrivateChats(),BotCommandScopeAllGroupChats()):await application.bot.get_my_commands(scope=scope)
    except Exception:log.exception("COMMAND_MENU_VERIFY_FAILED")
def _install_live_runtime_bridges(application):
    """Startup owns lifecycle; activate the autonomous registry dispatcher once."""
    if application.bot_data.get("_midnight_human_bridge_registered"):
        log.info("LIVE_CHAT_BRIDGE_ALREADY_REGISTERED | owner=bot")
    else:
        log.info("LIVE_CHAT_BRIDGE_DELEGATED | owner=bot_entrypoint")
    if not application.bot_data.get("_midnight_autonomous_scheduler_registered"):
        try:
            from handlers.autonomous_scheduler import register as register_autonomous_scheduler
            if register_autonomous_scheduler(application):
                log.info("AUTONOMOUS_SCHEDULER_ACTIVE | delivery=chat_registry")
        except Exception:
            log.exception("AUTONOMOUS_SCHEDULER_REGISTRATION_FAILED")
async def _stop_oracle_scheduler():
    scheduler=(_app.bot_data.get("oracle_scheduler") if _app else None)
    if scheduler is not None:
        try:
            result=scheduler.scheduler.shutdown(wait=False)
            if asyncio.iscoroutine(result):await result
        except Exception:log.exception("ORACLE_SCHEDULER_SHUTDOWN_FAILED")
    db=(_app.bot_data.get("oracle_db") if _app else None)
    if db is not None:
        try:await db.close()
        except Exception:log.exception("ORACLE_DATABASE_CLOSE_FAILED")
async def _graceful_shutdown():
    global _shutting_down
    if _shutting_down:return
    _shutting_down=True
    if _lease_task and not _lease_task.done():_lease_task.cancel()
    await _stop_oracle_scheduler()
    if _app:
        try:
            if _app.updater and _app.updater.running:await _app.updater.stop()
            if _app.running:await _app.stop()
            await _app.shutdown()
        except Exception:log.exception("APPLICATION_SHUTDOWN_FAILED")
    await _release_lease()
    if _health_server:threading.Thread(target=_health_server.shutdown,daemon=True).start()
async def run(application,storage_client=None):
    global _storage,_app,_lease_task
    _storage=storage_client;_app=application;loop=asyncio.get_running_loop();_install_signal_handlers(loop);start_health_server()
    if not await _wait_for_lease():return
    _lease_task=asyncio.create_task(_lease_heartbeat_loop())
    try:
        await application.initialize();_install_jobqueue_compat()
        if application.post_init:await application.post_init(application)
        _install_live_runtime_bridges(application);await application.start();await application.bot.get_me();await _verify_command_menu(application)
        await application.updater.start_polling(drop_pending_updates=True,allowed_updates=None);await asyncio.Event().wait()
    except asyncio.CancelledError:pass
    except Exception:log.exception("Fatal error in polling loop")
    finally:await _graceful_shutdown()
def init(storage_client=None):
    global _storage;_storage=storage_client
async def _wait_for_lease():
    deadline=time.time()+_LEASE_WAIT_MAX
    while time.time()<deadline:
        if await _acquire_lease():return True
        await asyncio.sleep(min(5,max(0,deadline-time.time())))
    return False
