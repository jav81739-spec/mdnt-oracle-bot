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

_GOSSIP_FORMS=("rumour","oddity","midnight_thought","found_thread","tiny_confession","curious_turn","unfinished_clue")

_STORY_SCENES=(
    ("At 02:17, the night watchman at a railway station heard a suitcase ring.","It was an old brown suitcase, locked, abandoned beside platform four. The strange part was that nobody had put a phone inside it.","He opened the case and found dozens of postcards, each dated exactly one year apart. Every card showed the same station, photographed from a different angle.","On the back of the newest card, someone had written tomorrow's date and one sentence: 'Leave the light on this time.'","He did. Nothing supernatural happened. At 02:19, an old woman walked in, looked at the light, and quietly said she had finally found the right year."),
    ("The librarian noticed that one book kept returning to the wrong shelf.","It was a thin blue novel nobody had borrowed in years. Every morning it appeared between completely unrelated books, as if someone had moved it during the night.","On the seventh morning she opened it and found a pencil mark beside a sentence she had never noticed before: 'Some doors only look like walls when you are in a hurry.'","She spent her lunch break walking through the building, looking at every wall she had stopped seeing years ago.","Behind a filing cabinet she found a narrow door, a forgotten reading room, and a handwritten note from the librarian who had worked there forty years earlier. It simply said, 'You took your time.'"),
    ("A taxi driver picked up a passenger who asked to be taken to a street that had disappeared twenty years ago.","The driver laughed, checked the map twice, and then realised he knew exactly where the passenger meant.","They drove past a supermarket, a school and a row of new apartments. At the end of the road stood one untouched blue gate.","The passenger paid before getting out. The note attached to the money carried the driver's own handwriting, although he had never seen it before.","He kept the note. Years later, whenever someone asked him about that night, he never mentioned the impossible part. He only said the city sometimes forgets things before people do."),
    ("Every evening, a woman in a yellow coat left a cup of tea on an empty park bench.","Nobody knew for whom. She never waited beside it. She simply placed the cup down and walked home before the streetlights came on.","One rainy night a curious teenager followed her and found a tiny brass plaque underneath the bench, almost hidden by rust.","It carried the name of a man and a date from forty-three years earlier. The teenager searched the local archive and found one photograph of him sitting on that exact bench.","The next evening the teenager left the tea instead. The woman in the yellow coat saw it, smiled without surprise, and sat down for the first time."),
    ("The astronomer found a new point of light just above the horizon.","It appeared for eleven seconds every night and vanished before any telescope could properly resolve it.","After three weeks she stopped trying to prove what it was and started writing down what she felt whenever it appeared: homesickness, then calm, then an odd certainty that someone had remembered her.","The next night the light did not appear. Instead, an envelope was waiting beneath the observatory door.","Inside was a photograph of the same sky taken by her father decades earlier, with one line on the back: 'You were always looking up.' She kept observing, but she stopped demanding that the sky explain itself."),
    ("The old watchmaker repaired a clock that had stopped at 11:48 every winter.","He replaced the spring, cleaned the gears and tested it for three days. It kept perfect time.","Then winter returned and the hands stopped again. Annoyed, he opened the back and found a tiny folded photograph tucked beneath the mechanism.","It showed his workshop as it had looked when he was a child, with his father standing in the doorway. On the wall behind him was the same clock.","He put the photograph back. The clock started ticking. He never repaired it again; some things, he decided, were allowed to keep one secret."),
    ("A girl found a voicemail on a phone that had been disconnected for years.","The message lasted nine seconds. There was traffic in the background, a dog barking, and someone laughing very softly.","At first she assumed it was a glitch. Then she recognised the laugh from an old family recording.","She played the message for her mother, who went completely still. She knew the voice too, but neither of them tried to explain how it had arrived.","They listened once more, then deleted it together. Some mysteries become smaller when you solve them, and some become more precious when you don't."),
    ("The rain stopped falling over one particular house but nowhere else in the neighbourhood.","For twenty minutes the clouds opened around it like a hole cut into the sky. Children ran into the street to stare.","Inside, the family kept eating dinner. They could hear the rain on every other roof and the silence above their own.","Then the youngest child noticed an old photograph on the fridge showing the same house, the same table, and the same impossible patch of dry sky.","Nobody had ever remembered taking the photograph. The rain returned a minute later, and the family decided not to throw the picture away."),
)

_MEMORY_SAFE_PATTERNS=(re.compile(r"\bmy favorite (?:movie|film|song|book|game|food|color|colour) is\s+(.+)",re.I),re.compile(r"\bi (?:really )?(?:like|love|prefer)\s+(.+)",re.I),re.compile(r"\bi(?:'m| am) a fan of\s+(.+)",re.I),re.compile(r"\bcall me\s+([\w .'-]{1,80})",re.I))
_SENSITIVE_MARKERS=re.compile(r"\b(password|otp|pin|cvv|bank|account number|card number|medical|diagnos|medicine|political party|religion|sexual|address|passport|aadhaar|ssn)\b",re.I)

def _seed(*parts:Any)->int:return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(),16)

def _footer()->str:return "🌙 *— Midnight Oracle*"

def generate_gossip(seed:str|None=None)->CreativePiece:
    """Create varied, social-feeling world gossip without targeting real people."""
    actual_seed=str(seed or time.time_ns());rng=random.Random(_seed(actual_seed,"gossip-v3"))
    form=rng.choice(_GOSSIP_FORMS);theme=rng.choice(_WORLD_THEMES);lead,tail=rng.choice(_GOSSIP_BITS)
    if form=="rumour":body=f"{lead}\n\n{tail}"
    elif form=="oddity":body=rng.choice((f"Here's a strange little thing: {tail} It somehow circles back to *{theme}*.",f"The odd part about *{theme}* is that the best stories are usually hiding in the boring details. {tail}"))
    elif form=="midnight_thought":body=rng.choice((f"Random midnight thought: *{theme}* has a habit of making ordinary things feel suspiciously interesting.",f"I keep thinking about *{theme}*. Not because it makes sense. Mostly because it doesn't quite stop being interesting."))
    elif form=="found_thread":body=rng.choice((f"I wandered into a strange little corner of *{theme}* and found this: {tail}",f"There is a thread connecting *{theme}* to a surprisingly ordinary question: why do some stories refuse to disappear?"))
    elif form=="tiny_confession":body=rng.choice((f"Tiny Oracle confession: I have a weakness for *{theme}* when one small detail refuses to behave normally.",f"Confession: give me one unexplained detail in *{theme}* and I will immediately start inventing three harmless theories."))
    elif form=="curious_turn":body=f"The funny thing about *{theme}* is that it starts ordinary and then takes one very strange turn. {tail}"
    else:body=rng.choice((f"There is a clue hiding somewhere in the story of *{theme}*. Nobody seems to agree what it means yet.",f"One small detail about *{theme}* keeps getting overlooked. Maybe that's why it is the interesting part."))
    endings=("Anyway. I thought the room deserved that little mystery. 🌙","File that under: things worth thinking about after midnight.","No conclusion yet. Which, honestly, makes it better.","The Oracle has theories. The Oracle is keeping the best one to itself. 👀","That is probably enough mystery for one message. Probably.")
    text=f"☾ *MIDNIGHT GOSSIP*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n{body}\n\n_{rng.choice(endings)}_\n\n{_footer()}"
    return CreativePiece("gossip",text,actual_seed)

def generate_story(seed:str|None=None)->CreativePiece:
    """Create a self-contained micro-story for fallback use; avoid stitched topic templates."""
    actual_seed=str(seed or time.time_ns());rng=random.Random(_seed(actual_seed,"story-v3"))
    scene=rng.choice(_STORY_SCENES)
    paragraphs=[scene[0],f"{scene[1]} {scene[2]}",f"{scene[3]} {scene[4]}"]
    text=f"☾ *MIDNIGHT STORY*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"+"\n\n".join(paragraphs)+f"\n\n{_footer()}"
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
    if strategy=="story":rule="Create a tiny original fictional story with a strong opening, a turn and a memorable closing."
    elif strategy=="gossip":rule="Create playful fictional gossip about an idea, mystery, culture, object, place or strange fact. Never about a group member. Never present invented claims as real news. Do not add a safety disclaimer unless needed. Avoid topic labels, 'rabbit hole' headings, fixed openings, fixed closings, and repeated meta-gossip phrases. Choose a natural social shape: a rumour, oddity, curious observation, tiny confession, found thread, unfinished clue, or spontaneous thought."
    elif strategy=="playful_observation":rule="Make one playful, harmless observation about the public conversational atmosphere, without naming, profiling or targeting members."
    else:rule="Make one genuinely interesting conversation-opening thought tied to the public topic; avoid generic greetings and avoid pretending to know private facts."
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
