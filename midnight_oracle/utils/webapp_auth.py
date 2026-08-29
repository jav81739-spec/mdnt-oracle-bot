"""Telegram Mini App initData HMAC validation."""
from __future__ import annotations
import hashlib,hmac,urllib.parse,time
from ..config import BOT_TOKEN

def validate_init_data(init_data:str,max_age_seconds:int=86400)->dict[str,str]:
    """Validate Telegram WebApp initData and return its key/value fields."""
    pairs=dict(urllib.parse.parse_qsl(init_data,keep_blank_values=True)); received=pairs.pop('hash',None)
    if not received: raise ValueError('missing hash')
    auth_key=hmac.new(b'WebAppData',BOT_TOKEN.encode(),hashlib.sha256).digest(); check=hmac.new(auth_key,'\n'.join(f'{k}={pairs[k]}' for k in sorted(pairs)).encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(check,received): raise ValueError('invalid signature')
    if 'auth_date' in pairs and time.time()-int(pairs['auth_date'])>max_age_seconds: raise ValueError('expired initData')
    return pairs
