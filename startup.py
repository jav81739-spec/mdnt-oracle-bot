"""
startup.py — Midnight Oracle canonical startup manager.

Keeps one polling owner, stale-lease recovery, graceful shutdown, health
checks, chat discovery, and all Telegram update types required by the durable
Phase 1–5 surface.
"""
from __future__ import annotations
import asyncio,json,logging,os,signal,socket,threading,time
from typing import Optional
from http.server import BaseHTTPRequestHandler,HTTPServer
log=logging.getLogger("midnight.startup")
_LEASE_KEY="midnight:polling_lease";_LEASE_TTL=60;_LEASE_REFRESH=20;_LEASE_WAIT_MAX=90;_INSTANCE_ID=f"{socket.gethostname()}:{os.getpid()}";_storage=None;_app=None;_lease_task:Optional[asyncio.Task]=None;_health_server:Optional[HTTPServer]=None;_shutting_down=False
async def _store_get(key:str)->Optional[str]:
    try:
        if _storage is None:return None
        result=_storage.get(key)
        if asyncio.iscoroutine(result):result=await result
        return result
    except Exception as exc:log.debug("storage.get(%s) failed: %s",key,exc);return None
async def _store_set(key:str,value:str,ttl:int=0)->bool:
    try:
        if _storage is None:return False
        result=_storage.setex(key,ttl,value) if ttl else _storage.set(key,value)
        if asyncio.iscoroutine(result):await result
        return True
    except Exception as exc:log.debug("storage.set(%s) failed: %s",key,exc);return False
async def _store_setnx(key:str,value:str,ttl:int)->bool:
    try:
        if _storage is None:return False
        setter=getattr(_storage,"setnx",None)
        if setter is None:return False
        result=setter(key,value,ttl=ttl)
        if asyncio.iscoroutine(result):result=await result
        return bool(result)
    except Exception as exc:log.debug("storage.setnx(%s) failed: %s",key,exc);return False
async def _store_compare_set(key:str,expected:str,value:str,ttl:int)->bool:
    try:
        if _storage is None:return False
        setter=getattr(_storage,"compare_set",None)
        if setter is None:return False
        result=setter(key,expected,value,ttl=ttl)
        if asyncio.iscoroutine(result):result=await result
        return bool(result)
    except Exception as exc:log.debug("storage.compare_set(%s) failed: %s",key,exc);return False
async def _store_compare_delete(key:str,expected:str)->bool:
    try:
        if _storage is None:return False
        evaluator=getattr(_storage,"eval",None)
        if callable(evaluator):
            script="if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"
            result=evaluator(script,[key],[expected])
            if asyncio.iscoroutine(result):result=await result
            return bool(int(result or 0))
        log.error("storage.compare_delete is unavailable; refusing unsafe lease deletion")
        return False
    except Exception as exc:log.debug("storage.compare_delete(%s) failed: %s",key,exc);return False
async def _store_delete(key:str)->bool:
    try:
        if _storage is None:return False
        result=_storage.delete(key)
        if asyncio.iscoroutine(result):await result
        return True
    except Exception as exc:log.debug("storage.delete(%s) failed: %s",key,exc);return False
async def _refresh_lease(raw:str|None=None)->bool:
    current=raw if raw is not None else await _store_get(_LEASE_KEY)
    if not current:return False
    try:
        info=json.loads(current)
        if info.get("instance")!=_INSTANCE_ID:return False
    except Exception:return False
    replacement=json.dumps({"instance":_INSTANCE_ID,"ts":time.time()})
    return await _store_compare_set(_LEASE_KEY,current,replacement,_LEASE_TTL)
async def _acquire_lease()->bool:
    raw=await _store_get(_LEASE_KEY)
    if raw:
        try:
            info=json.loads(raw);owner=info.get("instance");age=time.time()-info.get("ts",0)
            if owner==_INSTANCE_ID:return await _refresh_lease(raw)
            if age<_LEASE_TTL:log.info("POLLING_LEASE held by %s (age %.0fs, TTL %ds)",owner,age,_LEASE_TTL);return False
            log.warning("Stale lease from %s (age %.0fs > TTL %ds) — reclaiming",owner,age,_LEASE_TTL)
        except Exception:pass
    token=json.dumps({"instance":_INSTANCE_ID,"ts":time.time()})
    if await _store_setnx(_LEASE_KEY,token,_LEASE_TTL):
        log.info("Polling lease acquired by %s",_INSTANCE_ID);return True
    return False
async def _release_lease():
    raw=await _store_get(_LEASE_KEY)
    if raw:
        try:
            if json.loads(raw).get("instance")==_INSTANCE_ID:
                if await _store_compare_delete(_LEASE_KEY,raw):log.info("Polling lease released by %s",_INSTANCE_ID)
                else:log.warning("Polling lease release skipped because ownership could not be verified atomically")
                return
        except Exception:pass
    log.debug("Lease not owned by us — skipping release")
async def _lease_heartbeat_loop():
    while not _shutting_down:
        await asyncio.sleep(_LEASE_REFRESH)
        if _shutting_down:break
        try:
            if not await _refresh_lease():
                log.error("Polling lease ownership lost — stopping Telegram runtime")
                await _graceful_shutdown()
                break
        except Exception as exc:log.warning("Lease refresh failed: %s",exc)
async def _wait_for_lease()->bool:
    deadline=time.time()+_LEASE_WAIT_MAX
    while time.time()<deadline:
        if await _acquire_lease():return True
        remaining=deadline-time.time();wait=min(5,remaining)
        if wait<=0:break
        log.info("POLLING_LEASE busy — waiting %.0fs (%.0fs remaining)",wait,remaining);await asyncio.sleep(wait)
    log.error("Could not acquire polling lease within %ds — giving up",_LEASE_WAIT_MAX);return False
_REGISTRY_KEY="midnight:chat_registry"
async def register_chat(chat_id:int,chat_type:str,title:str=""):
    if chat_type=="private":return
    try:
        raw=await _store_get(_REGISTRY_KEY);registry:dict=json.loads(raw) if raw else {};registry[str(chat_id)]={"type":chat_type,"title":title[:100],"seen":int(time.time())};await _store_set(_REGISTRY_KEY,json.dumps(registry,ensure_ascii=False))
    except Exception as exc:log.debug("register_chat failed: %s",exc)
async def get_chat_registry()->dict:
    try:
        raw=await _store_get(_REGISTRY_KEY);return json.loads(raw) if raw else {}
    except Exception:return {}
async def get_broadcast_targets(include_groups:bool=True,include_channels:bool=True)->list[int]:
    registry=await get_chat_registry();targets=[]
    for cid_str,info in registry.items():
        t=info.get("type","")
        if include_groups and t in ("group","supergroup"):targets.append(int(cid_str))
        elif include_channels and t=="channel":targets.append(int(cid_str))
    return targets
class _HealthHandler(BaseHTTPRequestHandler):
    def _respond(self,status:int,body:bytes,ctype:str="text/plain"):
        self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.end_headers()
        if self.command!="HEAD":self.wfile.write(body)
    def do_GET(self):
        if self.path in ("/","/health","/healthz"):
            status="shutting_down" if _shutting_down else "ok";code=503 if _shutting_down else 200;self._respond(code,json.dumps({"status":status,"instance":_INSTANCE_ID}).encode(),"application/json")
        elif self.path=="/ready":
            ready=(_app is not None) and (not _shutting_down);self._respond(200 if ready else 503,json.dumps({"ready":ready}).encode(),"application/json")
        else:self._respond(404,b'{"status":"not_found"}',"application/json")
    def do_HEAD(self):self.do_GET()
    def log_message(self,*_):return
class _ReuseHTTPServer(HTTPServer):allow_reuse_address=True
def start_health_server()->HTTPServer:
    global _health_server
    port=int(os.getenv("PORT","10000"));_health_server=_ReuseHTTPServer(("0.0.0.0",port),_HealthHandler);t=threading.Thread(target=_health_server.serve_forever,daemon=True,name="midnight-health");t.start();log.info("Health server listening on 0.0.0.0:%d",port);return _health_server
def _install_signal_handlers(loop:asyncio.AbstractEventLoop):
    def _handle_signal(signum,_frame):
        name=signal.Signals(signum).name;log.info("Received %s — initiating graceful shutdown",name);loop.call_soon_threadsafe(lambda:asyncio.ensure_future(_graceful_shutdown(),loop=loop))
    signal.signal(signal.SIGTERM,_handle_signal);signal.signal(signal.SIGINT,_handle_signal)
async def _graceful_shutdown():
    global _shutting_down
    if _shutting_down:return
    _shutting_down=True;log.info("Graceful shutdown started")
    if _lease_task and not _lease_task.done():
        _lease_task.cancel()
        try:await _lease_task
        except asyncio.CancelledError:pass
    if _app is not None:
        try:
            scheduler=_app.bot_data.get('oracle_scheduler')
            if scheduler and scheduler.scheduler.running:scheduler.scheduler.shutdown(wait=False)
            if _app.updater and _app.updater.running:await _app.updater.stop()
            if _app.running:await _app.stop()
            await _app.shutdown();log.info("Telegram application stopped")
        except Exception as exc:log.warning("Error stopping Telegram app: %s",exc)
    await _release_lease()
    if _health_server:threading.Thread(target=_health_server.shutdown,daemon=True).start()
    log.info("Graceful shutdown complete")
def _install_jobqueue_compat()->None:
    try:
        from telegram.ext import JobQueue
        if hasattr(JobQueue,"run_weekly"):return
        def run_weekly(self,callback,time,weekday=0,data=None,name=None,chat_id=None,user_id=None,job_kwargs=None):
            ptb_day=(int(weekday)+1)%7
            return self.run_daily(callback,time=time,days=(ptb_day,),data=data,name=name,chat_id=chat_id,user_id=user_id,job_kwargs=job_kwargs)
        JobQueue.run_weekly=run_weekly;log.info("JobQueue compatibility: installed run_weekly() adapter")
    except Exception as exc:log.exception("Could not install JobQueue compatibility adapter: %s",exc);raise
async def _verify_command_menu(application)->None:
    try:
        from telegram import BotCommandScopeAllPrivateChats,BotCommandScopeAllGroupChats
        for label,scope in (("private",BotCommandScopeAllPrivateChats()),("groups",BotCommandScopeAllGroupChats())):
            commands=await application.bot.get_my_commands(scope=scope);log.info("COMMAND_MENU_VERIFIED | scope=%s | count=%d | commands=%s",label,len(commands),",".join(c.command for c in commands))
    except Exception as exc:log.exception("COMMAND_MENU_VERIFY_FAILED | %r",exc)
def _install_live_runtime_bridges(application)->None:
    """Explicitly install the canonical human-chat and autonomous social surfaces.

    This is deliberately done by the canonical startup manager rather than relying
    on import-time monkey patches, so Render's real process always gets the same
    handlers and social jobs.
    """
    try:
        from telegram.ext import MessageHandler,filters
        from handlers.live_chat_bridge import handle_live_chat
        marker="_midnight_human_bridge_registered"
        if not application.bot_data.get(marker):
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_live_chat),group=-40);application.bot_data[marker]=True;log.info("HUMAN_CHAT_BRIDGE_READY | dm=on | groups=on | fallback=off")
        from handlers import social_engine
        social_engine.init_storage(_storage)
        try:
            from core.public_output_guard import guard_post
            guard_marker="_midnight_public_output_guard_installed"
            if not application.bot_data.get(guard_marker):
                social_engine._post=guard_post(social_engine._post)
                application.bot_data[guard_marker]=True
                log.info("PUBLIC_OUTPUT_GUARD_READY | expressive=on")
        except Exception:
            log.exception("PUBLIC_OUTPUT_GUARD_INSTALL_FAILED")
        track_marker="_midnight_social_member_tracker_registered"
        if not application.bot_data.get(track_marker):
            application.add_handler(MessageHandler(filters.ChatType.GROUPS,social_engine.track_member),group=-39);application.bot_data[track_marker]=True;log.info("SOCIAL_MEMBER_REGISTRY_READY")
        social_engine.register_jobs(application)
        log.info("AUTONOMOUS_SOCIAL_ENGINE_READY | scheduled=19 | dynamic_group_targets=on")
    except Exception:
        log.exception("LIVE_RUNTIME_BRIDGE_INSTALL_FAILED")
async def run(application,storage_client=None):
    global _storage,_app,_lease_task
    if not logging.root.handlers:logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s",level=logging.INFO)
    _storage=storage_client;_app=application;loop=asyncio.get_running_loop();_install_signal_handlers(loop);start_health_server()
    if not await _wait_for_lease():log.critical("Cannot start: polling lease unavailable. Exiting.");return
    _lease_task=asyncio.ensure_future(_lease_heartbeat_loop());log.info("Starting Telegram polling — instance %s",_INSTANCE_ID)
    try:
        await application.initialize();_install_jobqueue_compat()
        if application.post_init is not None:await application.post_init(application)
        _install_live_runtime_bridges(application)
        await application.start();await application.bot.get_me();await _verify_command_menu(application)
        await application.updater.start_polling(drop_pending_updates=False,allowed_updates=["message","edited_message","callback_query","chat_member","my_chat_member","poll_answer","poll","inline_query"]);await asyncio.Event().wait()
    except asyncio.CancelledError:pass
    except Exception as exc:log.exception("Fatal error in polling loop: %s",exc)
    finally:await _graceful_shutdown()
def init(storage_client=None):
    global _storage
    _storage=storage_client
