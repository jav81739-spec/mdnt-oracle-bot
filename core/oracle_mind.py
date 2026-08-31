"""Midnight Oracle Mind: provider-independent memory, creativity and fallback intelligence."""
from __future__ import annotations
import hashlib, random, re, time
from dataclasses import dataclass
from typing import Any
from .ai import AIUnavailable, service

@dataclass(frozen=True)
class CreativePiece:
    kind: str
    text: str
    seed: str

_WORLD_THEMES=("lost cities and archaeological puzzles","deep ocean mysteries","strange weather and atmospheric phenomena","old maps and places that changed names","night trains and cities that never quite sleep","folklore that travelled between cultures","odd inventions that arrived before their time","astronomy, eclipses and the scale of the universe","cognitive biases and the tricks attention plays","libraries, forgotten manuscripts and marginalia","unexpected scientific discoveries","music scenes that changed a city's identity","beautifully useless inventions","ancient games and how people entertained themselves","the psychology of rumours and why stories spread")
_GOSSIP_FRAGMENTS=("Apparently the moon has been keeping receipts.","There is a rumour that Tuesday has been pretending to be Friday.","Someone, somewhere, is absolutely overthinking a three-word message.","The oldest argument in the universe is apparently still unresolved.","A librarian somewhere has definitely judged a book by its cover.","The night shift has its own unofficial mythology.","Scientists can measure astonishing things and still lose their keys.","A perfectly ordinary street probably has a story nobody has written down yet.","Somewhere a cat has become the unofficial manager of a household.","The universe continues to refuse to explain its group chat.")
_STORY_OPENERS=("At 02:17, a city discovered that one of its clocks was always four minutes ahead.","The letter arrived without a stamp, a sender, or any explanation.","Every night the same train stopped at a platform that did not exist on the map.","A small library kept one locked shelf that nobody remembered installing.","The astronomer noticed one star that seemed to blink in punctuation marks.","On the first morning of winter, every umbrella in town turned inside out at once.")
_STORY_TURNS=("Nobody agreed on what it meant, so they did what humans usually do: they invented a story.","The obvious explanation was wrong. The second obvious explanation was worse.","By sunrise, the rumour had become three rumours and one very convincing lie.","The clue was tiny enough to miss and strange enough to remember.","Someone finally asked the one question everyone else had been avoiding.","The truth turned out to be less dramatic, but somehow more beautiful.")
_STORY_ENDINGS=("And that is how a completely ordinary night became a story people kept retelling.","No one solved the mystery. They simply got better at living with it.","The clock was repaired. The story was not.","Years later, nobody remembered the explanation. Everyone remembered the night.","The last person to leave switched off the light and left the mystery where it belonged.")
_MEMORY_SAFE_PATTERNS=(re.compile(r"\bmy favorite (?:movie|film|song|book|game|food|color|colour) is\s+(.+)",re.I),re.compile(r"\bi (?:really )?(?:like|love|prefer)\s+(.+)",re.I),re.compile(r"\bi(?:'m| am) a fan of\s+(.+)",re.I),re.compile(r"\bcall me\s+([\w .'-]{1,80})",re.I))
_SENSITIVE_MARKERS=re.compile(r"\b(password|otp|pin|cvv|bank|account number|card number|medical|diagnos|medicine|political party|religion|sexual|address|passport|aadhaar|ssn)\b",re.I)

def _seed(*parts:Any)->int:return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(),16)

def generate_gossip(seed:str|None=None)->CreativePiece:
    rng=random.Random(_seed(seed or time.time_ns(),"gossip"));theme=rng.choice(_WORLD_THEMES);fragment=rng.choice(_GOSSIP_FRAGMENTS)
    text=f"☾ *MIDNIGHT GOSSIP*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n{fragment}\n\nTonight's suspicious subject: *{theme}*.\n\n_No group member is involved. This is an Oracle-made rumour for the room, not a claim about a real person._\n\n🌙 *— Midnight Oracle*"
    return CreativePiece("gossip",text,str(seed or time.time_ns()))

def generate_story(seed:str|None=None)->CreativePiece:
    rng=random.Random(_seed(seed or time.time_ns(),"story"));opener,turn,ending=rng.choice(_STORY_OPENERS),rng.choice(_STORY_TURNS),rng.choice(_STORY_ENDINGS);theme=rng.choice(_WORLD_THEMES)
    text=f"☾ *MIDNIGHT STORY*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n_{opener}_\n\nThe night had the texture of *{theme}*.\n\n{turn}\n\n_{ending}_\n\n✦ _Original Oracle fiction — not a report of a real event._\n\n🌙 *— Midnight Oracle*"
    return CreativePiece("story",text,str(seed or time.time_ns()))

def _language_hint(items:list[dict[str,Any]])->str:
    joined=" ".join(str(x.get("text","")) for x in items[-10:]).lower()
    hindi=sum(1 for token in (" hai "," hain "," yaar "," bhai "," kya "," nahi "," nahi "," tum "," mujhe "," aaj "," kal "," bas "," suno ") if token in f" {joined} ")
    latin=len(re.findall(r"\b(the|and|is|are|what|why|how|this|that|you|we|I)\b",joined))
    if hindi>latin:return "natural Hinglish; Hindi/English mix, not translation"
    if hindi and latin:return "balanced natural Hinglish/English mix"
    return "natural English"

async def generate_contextual_piece(context_items:list[dict[str,Any]], seed:str|None=None)->CreativePiece:
    """Generate a fresh room-relevant story/gossip idea without using member memory."""
    clean=[str(x.get("text",""))[:300] for x in context_items[-8:] if str(x.get("text","" )).strip()]
    hint=_language_hint(context_items)
    fallback=generate_story(seed) if random.SystemRandom().random()<0.55 else generate_gossip(seed)
    if not clean:return fallback
    prompt=("You are Midnight Oracle. Create ONE original, harmless, non-invasive spontaneous idea for a Telegram group. "
            "Use the recent public conversation only as topical atmosphere; never mention, profile, expose, diagnose, or gossip about a member. "
            f"Language: {hint}. Keep it conversational, premium, concise, and relevant to the room. It can be a tiny fictional story, playful observation, curious question, or harmless world-style gossip. "
            "Do not claim private knowledge or fabricate real breaking news. Do not use a generic greeting. Return only the message.\nRecent public conversation:\n"+"\n".join(f"- {x}" for x in clean))
    try:
        generated=await service.generate(prompt,timeout=20.0)
        generated=(generated or "").strip()[:2200]
        if generated:return CreativePiece("contextual",generated,str(seed or time.time_ns()))
    except (AIUnavailable,TimeoutError,Exception):pass
    return fallback

def extract_safe_memory(text:str)->str|None:
    value=(text or "").strip()
    if not value or _SENSITIVE_MARKERS.search(value):return None
    for pattern in _MEMORY_SAFE_PATTERNS:
        match=pattern.search(value)
        if match:return re.sub(r"\s+"," ",match.group(0)).strip()[:240]
    return None

async def save_explicit_memory(db,user_id:int,group_id:int,text:str)->bool:
    fact=extract_safe_memory(text)
    if not fact:return False
    await db.execute("INSERT INTO oracle_memory(user_id,group_id,memory_type,content,importance,created_at,last_used_at) VALUES(?,?,?,?,?,?,?)",(int(user_id),int(group_id),"semantic",fact,0.7,time.time(),0.0))
    await db.execute("DELETE FROM oracle_memory WHERE id NOT IN (SELECT id FROM oracle_memory WHERE user_id=? AND group_id=? ORDER BY importance DESC,created_at DESC LIMIT 40) AND user_id=? AND group_id=?",(int(user_id),int(group_id),int(user_id),int(group_id)))
    return True

async def recall_memories(db,user_id:int,group_id:int,limit:int=6)->list[str]:
    rows=await db.fetchall("SELECT id,content FROM oracle_memory WHERE user_id=? AND group_id=? ORDER BY importance DESC,last_used_at ASC,created_at DESC LIMIT ?",(int(user_id),int(group_id),max(1,min(12,int(limit)))))
    ids=[int(row[0]) for row in rows]
    if ids:
        marks=",".join("?" for _ in ids);await db.execute(f"UPDATE oracle_memory SET last_used_at=? WHERE id IN ({marks})",(time.time(),*ids))
    return [str(row[1]) for row in rows]

def local_reply(text:str,history:list[dict[str,Any]]|None=None,memories:list[str]|None=None)->str:
    value=(text or "").strip();low=value.casefold()
    if not value:return "I'm here. 🌙"
    if any(token in low for token in ("sad","upset","rough","bad day","not okay","😭","🥲")):return "Haan… bol. Main sun raha hoon. 🖤"
    if any(token in low for token in ("lol","haha","😂","🤣")):return "😂 Okay, that one actually got me."
    if "gossip" in low:return generate_gossip().text
    if "story" in low or "kahani" in low:return generate_story().text
    if "?" in value:return random.Random(_seed(value,len(history or []))).choice(("Hmm. I have a thought on that.","Haan — interesting question. 🌙","Wait, there's actually a fun angle here."))
    if memories:return random.Random(_seed(value,memories[0])).choice(("Hmm… I'm with you.","Yeah. Keep going, I'm listening. 🌙","I see where you're going."))
    return random.Random(_seed(value,time.time_ns()//10_000_000)).choice(("Hmm. Tell me more.","I'm here. Bol.","Yeah… I'm listening. 🌙","Okay, I'm following.","Go on. 👀"))

async def generate_or_fallback(prompt:str,fallback_text:str)->str:
    try:return await service.generate(prompt,timeout=20.0)
    except (AIUnavailable,TimeoutError,Exception):return fallback_text
