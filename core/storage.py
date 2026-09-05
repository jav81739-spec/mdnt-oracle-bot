"""Durable async storage for Midnight Oracle."""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import quote

import httpx

log = logging.getLogger("midnight.storage")


class StorageError(RuntimeError):
    """Raised when a required persistent operation cannot be completed."""


class Storage:
    """Provide one durable asynchronous key-value storage facade."""
    def __init__(self, url: str | None = None, token: str | None = None, timeout: float = 8.0, retries: int = 2) -> None:
        self.url=(url or os.getenv("UPSTASH_REDIS_REST_URL","")).rstrip("/"); self.token=token or os.getenv("UPSTASH_REDIS_REST_TOKEN",""); self.timeout=max(1.0,float(timeout)); self.retries=max(0,int(retries)); self._client: httpx.AsyncClient|None=None; self._local:dict[str,Any]={}; self._local_expiry:dict[str,float]={}; self._local_lists:dict[str,list[str]]={}; self._local_lock=asyncio.Lock(); self._closed=False
    @property
    def configured(self)->bool:return bool(self.url and self.token)
    async def start(self)->None:
        if self._client is None and self.configured:self._client=httpx.AsyncClient(timeout=httpx.Timeout(self.timeout,connect=min(4.0,self.timeout)),headers={"Authorization":f"Bearer {self.token}"})
        self._closed=False
    async def close(self)->None:
        self._closed=True; client,self._client=self._client,None
        if client is not None:await client.aclose()
    async def _request(self,method:str,path:str="/",**kwargs:Any)->Any:
        if not self.configured:raise StorageError("persistent storage is not configured")
        await self.start(); assert self._client is not None; last:Exception|None=None
        for attempt in range(self.retries+1):
            try:
                response=await self._client.request(method,f"{self.url}{path}",**kwargs); response.raise_for_status(); payload=response.json()
                if isinstance(payload,dict) and payload.get("error"):raise StorageError(str(payload["error"]))
                return payload.get("result") if isinstance(payload,dict) else payload
            except (httpx.HTTPError,ValueError,StorageError) as exc:
                last=exc
                if attempt>=self.retries:break
                await asyncio.sleep(0.15*(2**attempt))
        raise StorageError(f"storage request failed after {self.retries+1} attempts") from last
    async def _command(self,*parts:Any)->Any:return await self._request("POST","/",json=[str(p) for p in parts])
    async def get(self,key:str,default:Any=None)->Any:
        if not self.configured:
            async with self._local_lock:self._expire_local_locked();return self._local.get(key,default)
        try:
            result=await self._request("GET",f"/get/{quote(key,safe='')}");return default if result is None else result
        except StorageError:log.exception("GET failed for key=%s",key);return default
    async def load(self,key:str,default:Any=None)->Any:
        value=await self.get(key,None)
        if value is None:return default
        if isinstance(value,(dict,list,int,float,bool)):return value
        if isinstance(value,str):
            try:return json.loads(value)
            except (TypeError,ValueError):return default
        return default
    async def set(self,key:str,value:Any,ttl:int|None=None)->bool:
        try:encoded=json.dumps(value,ensure_ascii=False,separators=(",",":")) if not isinstance(value,str) else value
        except (TypeError,ValueError):log.exception("Could not serialize value for key=%s",key);return False
        if not self.configured:
            async with self._local_lock:
                self._local[key]=encoded
                if ttl is None:self._local_expiry.pop(key,None)
                else:self._local_expiry[key]=time.time()+max(1,int(ttl))
            return True
        try:
            result=await self._command("SET",key,encoded) if ttl is None else await self._command("SET",key,encoded,"EX",max(1,int(ttl)))
            return str(result).upper() in {"OK","TRUE","1"}
        except StorageError:log.exception("SET failed for key=%s",key);return False
    async def setex(self,key:str,ttl:int,value:Any)->bool:return await self.set(key,value,ttl=max(1,int(ttl)))
    async def save(self,key:str,value:Any,ttl:int|None=None)->bool:return await self.set(key,value,ttl=ttl)
    async def setnx(self,key:str,value:str,ttl:int=15)->bool:
        ttl=max(1,int(ttl))
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked()
                if key in self._local:return False
                self._local[key]=value;self._local_expiry[key]=time.time()+ttl;return True
        try:return str(await self._command("SET",key,value,"NX","EX",ttl)).upper() in {"OK","TRUE","1"}
        except StorageError:log.exception("SETNX failed for key=%s",key);return False
    async def compare_set(self,key:str,expected:str,value:str,ttl:int)->bool:
        ttl=max(1,int(ttl))
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked()
                if self._local.get(key)!=expected:return False
                self._local[key]=value;self._local_expiry[key]=time.time()+ttl;return True
        script="if redis.call('GET',KEYS[1])==ARGV[1] then redis.call('SET',KEYS[1],ARGV[2],'EX',ARGV[3]); return 1 end; return 0"
        try:return bool(int(await self._command("EVAL",script,1,key,expected,value,str(ttl)) or 0))
        except StorageError:log.exception("COMPARE_SET failed for key=%s",key);return False
    async def delete(self,*keys:str)->int:
        if not keys:return 0
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked();count=0
                for key in keys:
                    if key in self._local:count+=1
                    self._local.pop(key,None);self._local_expiry.pop(key,None);self._local_lists.pop(key,None)
                return count
        try:return int(await self._command("DEL",*keys) or 0)
        except StorageError:log.exception("DELETE failed for keys=%s",keys);return 0
    async def incrby(self,key:str,amount:int)->int:
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked();current=int(self._local.get(key,0) or 0)+int(amount);self._local[key]=str(current);return current
        return int(await self._command("INCRBY",key,int(amount)))
    async def eval(self,script:str,keys:list[str]|tuple[str,...]=(),args:list[str]|tuple[str,...]=())->Any:
        if not self.configured:raise StorageError("EVAL requires configured persistent storage")
        return await self._command("EVAL",script,len(keys),*keys,*args)
    async def atomic_transfer(self,sender_key:str,receiver_key:str,amount:int)->tuple[int,int]:
        amount=int(amount)
        if amount<=0:raise StorageError("transfer amount must be positive")
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked();sender=max(0,int(self._local.get(sender_key,0) or 0));receiver=max(0,int(self._local.get(receiver_key,0) or 0))
                if sender<amount:raise StorageError("insufficient balance")
                sender-=amount;receiver+=amount;self._local[sender_key],self._local[receiver_key]=str(sender),str(receiver);return sender,receiver
        script="local a=tonumber(ARGV[1]); local s=tonumber(redis.call('GET',KEYS[1]) or '0'); if s<a then return {0,-1,-1} end; local ns=s-a; local nr=tonumber(redis.call('GET',KEYS[2]) or '0')+a; redis.call('SET',KEYS[1],ns); redis.call('SET',KEYS[2],nr); return {1,ns,nr}"
        result=await self.eval(script,[sender_key,receiver_key],[str(amount)])
        if not isinstance(result,list) or len(result)!=3 or int(result[0])!=1:raise StorageError("insufficient balance")
        return int(result[1]),int(result[2])
    async def atomic_claim(self,balance_key:str,marker_key:str,amount:int,ttl:int)->tuple[bool,int]:
        amount,ttl=int(amount),max(1,int(ttl))
        if amount<0:raise StorageError("claim amount must not be negative")
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked()
                if marker_key in self._local:return False,int(self._local.get(balance_key,0) or 0)
                current=int(self._local.get(balance_key,0) or 0)+amount;self._local[balance_key]=str(current);self._local[marker_key]="1";self._local_expiry[marker_key]=time.time()+ttl;return True,current
        script="if redis.call('EXISTS',KEYS[2])==1 then return {0,tonumber(redis.call('GET',KEYS[1]) or '0')} end; redis.call('SET',KEYS[2],'1','EX',ARGV[2]); local n=redis.call('INCRBY',KEYS[1],ARGV[1]); return {1,n}"
        result=await self.eval(script,[balance_key,marker_key],[str(amount),str(ttl)])
        if not isinstance(result,list) or len(result)!=2:raise StorageError("invalid atomic claim response")
        return bool(int(result[0])),int(result[1])
    async def atomic_remove(self,key:str,amount:int)->int:
        amount=int(amount)
        if amount<0:raise StorageError("remove amount must not be negative")
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked();current=max(0,int(self._local.get(key,0) or 0))
                if current<amount:raise StorageError("insufficient balance")
                current-=amount;self._local[key]=str(current);return current
        script="local a=tonumber(ARGV[1]); local c=tonumber(redis.call('GET',KEYS[1]) or '0'); if c<a then return {0,c} end; c=c-a; redis.call('SET',KEYS[1],c); return {1,c}"
        result=await self.eval(script,[key],[str(amount)])
        if not isinstance(result,list) or len(result)!=2 or int(result[0])!=1:raise StorageError("insufficient balance")
        return int(result[1])
    async def scan(self,pattern:str="*",count:int=100)->list[str]:
        count=max(1,min(int(count),500))
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked();keys=set(self._local)|set(self._local_lists);return sorted(k for k in keys if fnmatch.fnmatchcase(k,pattern))
        found=[];cursor="0"
        try:
            while True:
                result=await self._command("SCAN",cursor,"MATCH",pattern,"COUNT",count)
                if not isinstance(result,list) or len(result)!=2:raise StorageError("invalid SCAN response")
                cursor,batch=str(result[0]),result[1] or [];found.extend(str(k) for k in batch)
                if cursor=="0":return found
        except StorageError:log.exception("SCAN failed for pattern=%s",pattern);return []
    async def lpush(self,key:str,*values:Any)->int:
        if not values:return 0
        if not self.configured:
            async with self._local_lock:
                items=self._local_lists.setdefault(key,[])
                for value in values:items.insert(0,str(value))
                return len(items)
        return int(await self._command("LPUSH",key,*values) or 0)
    async def lrange(self,key:str,start:int,end:int)->list[str]:
        if not self.configured:
            async with self._local_lock:
                items=self._local_lists.get(key,[]);return items[start:] if end==-1 else items[start:end+1]
        return list(await self._command("LRANGE",key,int(start),int(end)) or [])
    async def exists(self,key:str)->bool:
        if not self.configured:
            async with self._local_lock:self._expire_local_locked();return key in self._local or bool(self._local_lists.get(key))
        try:return bool(int(await self._command("EXISTS",key) or 0))
        except StorageError:log.exception("EXISTS failed for key=%s",key);return False
    async def ttl(self,key:str)->int:
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked();expiry=self._local_expiry.get(key)
                if key not in self._local and key not in self._local_lists:return -2
                if expiry is None:return -1
                return max(0,int(expiry-time.time()))
        try:return int(await self._command("TTL",key) or -2)
        except StorageError:log.exception("TTL failed for key=%s",key);return -2
    def _expire_local_locked(self)->None:
        now=time.time()
        for key,expiry in list(self._local_expiry.items()):
            if expiry<=now:self._local_expiry.pop(key,None);self._local.pop(key,None);self._local_lists.pop(key,None)
    @asynccontextmanager
    async def lock(self,key:str,ttl:int=60,wait:float=5)->AsyncIterator[bool]:
        """Acquire a distributed lock with ownership-safe release."""
        token=f"lock-{id(self)}-{time.monotonic_ns()}";deadline=time.monotonic()+max(0.0,float(wait));lock_key=f"lock:{key}";acquired=False
        if not self.configured:
            lock=_LOCAL_LOCKS.setdefault(key,asyncio.Lock())
            try:await asyncio.wait_for(lock.acquire(),timeout=max(0.0,float(wait)));acquired=True
            except asyncio.TimeoutError:acquired=False
            try:yield acquired
            finally:
                if acquired and lock.locked():lock.release()
            return
        while time.monotonic()<=deadline:
            if await self.setnx(lock_key,token,ttl=max(1,int(ttl))):acquired=True;break
            await asyncio.sleep(min(0.05,max(0.0,deadline-time.monotonic())))
        try:yield acquired
        finally:
            if acquired:
                script="if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"
                try:await self.eval(script,[lock_key],[token])
                except StorageError:log.exception("LOCK_RELEASE_FAILED | key=%s",key)

_LOCAL_LOCKS:dict[str,asyncio.Lock]={}
storage=Storage()
