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

_WORLD_THEMES=(
    "lost cities and archaeological puzzles","deep ocean mysteries","strange weather and atmospheric phenomena",
    "old maps and places that changed names","night trains and cities that never quite sleep",
    "folklore that travelled between cultures","odd inventions that arrived before their time",
    "astronomy, eclipses and the scale of the universe","cognitive biases and the tricks attention plays",
    "libraries, forgotten manuscripts and marginalia","unexpected scientific discoveries",
    "music scenes that changed a city's identity","beautifully useless inventions",
    "ancient games and how people entertained themselves","the psychology of rumours and why stories spread",
)

_GOSSIP_BITS=(
    ("Apparently, the moon has been keeping receipts.","Nobody has explained why the oldest maps always seem to leave one interesting corner blank."),
    ("Tiny piece of midnight gossip: Tuesday has been acting suspiciously like Friday lately.","The calendar refuses to comment."),
    ("There is a very convincing rumour that some abandoned places become more interesting after everyone stops looking for them.","Honestly, that feels unfair to the abandoned places."),
    ("Someone once decided that a perfectly ordinary object needed a much stranger purpose.","The original idea failed. The story survived."),
    ("The night shift has its own unofficial mythology.","Half the stories are probably exaggerated. The other half are better because nobody checked."),
    ("A forgotten manuscript can spend centuries being ignored and then one sentence changes everything.","That is a dangerous amount of power for a sentence."),
    ("Somewhere between fact and folklore, a story becomes too good to leave alone.","Midnight has always had a weakness for that border."),
    ("There are mysteries that survive not because they are impossible, but because the ordinary explanation is disappointingly boring.","Oracle votes for the interesting footnote."),
    ("A city can change its name, its borders and its skyline and still accidentally keep the same old ghost story.","Cities are terrible at throwing things away."),
    ("Scientists can measure astonishing things and still lose their keys.","Balance, apparently, is important."),
)

_GOSSIP_FORMS=(
    "rumour",
    "oddity",
    "midnight_thought",
    "found_thread",
    "tiny_confession",
    "curious_turn",
    "unfinished_clue",
)

_STORY_OPENERS=(
    "At 02:17, a city discovered that one of its clocks was always four minutes ahead.",
    "The letter arrived without a stamp, a sender, or any explanation.",
    "Every night the same train stopped at a platform that did not exist on the map.",
    "A small library kept one locked shelf that nobody remembered installing.",
    "The astronomer noticed one star that seemed to blink in punctuation marks.",
    "On the first morning of winter, every umbrella in town turned inside out at once.",
)
_STORY_TURNS=(
    "Nobody agreed on what it meant, so they did what humans usually do: they invented a story.",
    "The obvious explanation was wrong. The second obvious explanation was worse.",
    "By sunrise, the rumour had become three rumours and one very convincing lie.",
    "The clue was tiny enough to miss and strange enough to remember.",
    "Someone finally asked the one question everyone else had been avoiding.",
    "The truth turned out to be less dramatic, but somehow more beautiful.",
)
_STORY_ENDINGS=(
    "And that is how a completely ordinary night became a story people kept retelling.",
    "No one solved the mystery. They simply got better at living with it.",
    "The clock was repaired. The story was not.",
    "Years later, nobody remembered the explanation. Everyone remembered the night.",
    "The last person to leave switched off the light and left the mystery where it belonged.",
)
_MEMORY_SAFE_PATTERNS=(re.compile(r"\bmy favorite (?:movie|film|song|book|game|food|color|colour) is\s+(.+)",re.I),re.compile(r"\bi (?:really )?(?:like|love|prefer)\s+(.+)",re.I),re.compile(r"\bi(?:'m| am) a fan of\s+(.+)",re.I),re.compile(r"\bcall me\s+([\w .'-]{1,80})",re.I))
_SENSITIVE_MARKERS=re.compile(r"\b(password|otp|pin|cvv|bank|account number|card number|medical|diagnos|medicine|political party|religion|sexual|address|passport|aadhaar|ssn)\b",re.I)

def _seed(*parts:Any)->int:return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(),16)

def _footer()->str:return "🌙 *— Midnight Oracle*"

def generate_gossip(seed:str|None=None)->CreativePiece:
    """Create varied, social-feeling world gossip without targeting real people."""
    actual_seed=str(seed or time.time_ns());rng=random.Random(_seed(actual_seed,"gossip-v3"))
    form=rng.choice(_GOSSIP_FORMS)
    theme=rng.choice(_WORLD_THEMES)
    lead,tail=rng.choice(_GOSSIP_BITS)
    if form=="rumour":
        body=f"{lead}\n\n{tail}"
    elif form=="oddity":
        body=rng.choice((
            f"Here's a strange little thing: {tail} It somehow circles back to *{theme}*.",
            f"The odd part about *{theme}* is that the best stories are usually hiding in the boring details. {tail}",
        ))
    elif form=="midnight_thought":
        body=rng.choice((
            f"Random midnight thought: *{theme}* has a habit of making ordinary things feel suspiciously interesting.",
            f"I keep thinking about *{theme}*. Not because it makes sense. Mostly because it doesn't quite stop being interesting.",
        ))
    elif form=="found_thread":
        body=rng.choice((
            f"I wandered into a strange little corner of *{theme}* and found this: {tail}",
            f"There is a thread connecting *{theme}* to a surprisingly ordinary question: why do some stories refuse to disappear?",
        ))
    elif form=="tiny_confession":
        body=rng.choice((
            f"Tiny Oracle confession: I have a weakness for *{theme}* when one small detail refuses to behave normally.",
            f"Confession: give me one unexplained detail in *{theme}* and I will immediately start inventing three harmless theories.",
        ))
    elif form=="curious_turn":
        body=f"The funny thing about *{theme}* is that it starts ordinary and then takes one very strange turn. {tail}"
    else:
        body=rng.choice((
            f"There is a clue hiding somewhere in the story of *{theme}*. Nobody seems to agree what it means yet.",
            f"One small detail about *{theme}* keeps getting overlooked. Maybe that's why it is the interesting part.",
        ))
    endings=(
        "Anyway. I thought the room deserved that little mystery. 🌙",
        "File that under: things worth thinking about after midnight.",
        "No conclusion yet. Which, honestly, makes it better.",
        "The Oracle has theories. The Oracle is keeping the best one to itself. 👀",
        "That is probably enough mystery for one message. Probably.",
    )
    text=f"☾ *MIDNIGHT GOSSIP*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n{body}\n\n_{rng.choice(endings)}_\n\n{_footer()}"
    return CreativePiece("gossip",text,actual_seed)

def generate_story(seed:str|None=None)->CreativePiece:
    actual_seed=str(seed or time.time_ns());rng=random.Random(_seed(actual_seed,"story-v2"))
    opener,turn,ending=rng.choice(_STORY_OPENERS),rng.choice(_STORY_TURNS),rng.choice(_STORY_ENDINGS);theme=rng.choice(_WORLD_THEMES)
    text=f"☾ *MIDNIGHT STORY*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n_{opener}_\n\nThe night had the strange atmosphere of *{theme}*.\n\n{turn}\n\n_{ending}_\n\n{_footer()}"
    return CreativePiece("story",text,actual_seed)

def _language_hint(items:list[dict[str,Any]])->str:
    joined=" ".join(str(x.get("text","")) for x in items[-10:]).lower()
    hindi=sum(1 for token in (" hai "," hain "," yaar "," bhai "," kya "," nahi "," tum "," mujhe "," aaj "," kal "," bas "," suno ") if token in f" {joined} ")
    latin=len(re.findall(r"\b(the|and|is|are|what|why|how|this|that|you|we|I)\b",joined))
    if hindi>latin:return "natural Hinglish; Hindi/English mix, not translation"
    if hindi and latin:return "balanced natural Hinglish/English mix"
    return "natural English"

def language_hint(items:list[dict[str,Any]])->str:return _language_hint(items)

async def generate_contextual_piece(context_items:list[dict[str,Any]], seed:str|None=None, strategy:str="curiosity")->CreativePiece:
    """Generate one relevant Oracle presence while keeping member content non-invasive."""
    clean=[str(x.get("text",""))[:300] for x in context_items[-8:] if str(x.get("text","")).strip()]
    hint=_language_hint(context_items);strategy=(strategy or "curiosity").strip().lower();actual_seed=str(seed or time.time_ns())
    fallback=generate_story(actual_seed) if strategy=="story" else generate_gossip(actual_seed) if strategy=="gossip" else (generate_story(actual_seed) if random.SystemRandom().random()<0.5 else generate_gossip(actual_seed))
    if not clean:return fallback
    if strategy=="story": rule="Create a tiny original fictional story with a strong opening, a turn and a memorable closing."
    elif strategy=="gossip": rule="Create playful fictional gossip about an idea, mystery, culture, object, place or strange fact. Never about a group member. Never present invented claims as real news. Do not add a safety disclaimer unless needed. Avoid topic labels, 'rabbit hole' headings, fixed openings, fixed closings, and repeated meta-gossip phrases. Choose a natural social shape: a rumour, oddity, curious observation, tiny confession, found thread, unfinished clue, or spontaneous thought."
    elif strategy=="playful_observation": rule="Make one playful, harmless observation about the public conversational atmosphere, without naming, profiling or targeting members."
    else: rule="Make one genuinely interesting conversation-opening thought tied to the public topic; avoid generic greetings and avoid pretending to know private facts."
    prompt=("You are Midnight Oracle, a mysterious but warm social presence. Create ONE original message for a Telegram group. "
            "Use recent public conversation only as topical atmosphere. Never expose, profile, diagnose, target, or invent personal facts about members. "
            f"Language: {hint}. Strategy: {strategy}. {rule} "
            "The result must feel spontaneous, specific and human, not like a template, topic label, trivia heading, disclaimer, or AI explanation. "
            "For gossip, gossip about the world of ideas rather than people. For storytelling, tell a real-feeling piece of original fiction. "
            "Do not fabricate breaking news or attribute invented claims to real people. Do not explain your generation process. Return only the message.\nRecent public conversation:\n"
            +"\n".join(f"- {x}" for x in clean))
    try:
        generated=(await service.generate(prompt,timeout=20.0) or "").strip()[:2200]
        if generated:return CreativePiece(strategy,generated,actual_seed)
    except Exception:pass
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
    except Exception:return fallback_text
