"""Social relationship commands with Oracle-selected members."""
from __future__ import annotations
import random
from typing import Any
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention
from core.oracle_instinct import choose_one, choose_pair, explain_lens
from core.oracle_freshness import FreshnessGovernor
from handlers import social_engine

bestie_pairs: dict[int, Any] = {}
declared_besties: dict[int, dict[int, Any]] = {}
message_counts: dict[int, dict[int, dict[str, Any]]] = {}
DUO_PREFIXES = ["Chaos", "Dream", "Menace", "Golden", "Rogue", "Midnight", "Orbit"]
DUO_SUFFIXES = ["Duo", "Squad", "Twins", "Crew", "Pair", "Circuit"]
SHIP_VERDICTS = {
    "low": ["chaotic and doomed 💀", "friends at best, enemies at worst 😭", "the Oracle is unconvinced 🌘"],
    "mid": ["could work with effort 🤞", "50/50, coin-flip energy", "there is something here, maybe"],
    "high": ["written in the stars ✨", "unreasonably perfect together", "the room may have noticed first 🌙"],
}
ACTION_TEXT = {
    "hug": ["wraps {target} in a warm hug", "pulls {target} into a quiet hug", "sends {target} an unexpected hug"],
    "pat": ["gives {target} a gentle head pat", "pats {target} like they survived the day", "offers {target} a tiny reassuring pat"],
    "highfive": ["high-fives {target}", "meets {target} with a perfectly timed high-five", "raises a hand for {target} — your move"],
    "slap": ["gives {target} a theatrical slap", "delivers {target} one dramatically harmless slap", "bonks the timeline with a slap aimed at {target}"],
    "punch": ["throws a playful punch at {target}", "challenges {target} to one cartoon punch", "lands a completely unserious punch near {target}"],
    "kick": ["gives {target} a playful kick", "launches a cartoon kick toward {target}", "adds {target} to tonight's kick agenda"],
    "kiss": ["gives {target} a tiny dramatic kiss", "drops a playful kiss toward {target}", "sends {target} one suspiciously theatrical kiss"],
    "poke": ["pokes {target}", "tests whether {target} is still awake with a poke", "gives {target} exactly one annoying poke"],
    "cuddle": ["cuddles up with {target}", "pulls {target} into the comfort zone", "declares {target} temporarily cuddle-protected"],
    "bonk": ["bonks {target}", "bonks {target} with ceremonial precision", "issues {target} one gentle bonk"],
    "bite": ["playfully bites {target}", "gives {target} one ridiculous little bite", "marks {target} for tonight's chaos with a playful bite"],
    "wave": ["waves at {target}", "spots {target} and waves across the room", "quietly waves hello to {target}"],
    "wink": ["winks at {target}", "gives {target} one suspicious wink", "leaves {target} with a knowing wink"],
    "dance": ["dances with {target}", "pulls {target} into the night's tiny dance floor", "starts an impromptu dance beside {target}"],
    "cheer": ["cheers for {target}", "starts a tiny cheering section for {target}", "quietly puts {target} on tonight's victory board"],
    "comfort": ["comforts {target}", "sits beside {target} for a quiet moment", "reminds {target} that tonight can be softer"],
    "tickle": ["tickles {target}", "declares {target} dangerously ticklish", "launches one completely unserious tickle attack at {target}"],
    "salute": ["salutes {target}", "gives {target} a midnight salute", "formally acknowledges {target} with a salute"],
    "stare": ["stares dramatically at {target}", "locks eyes with {target} for no explained reason", "lets the silence stare back at {target}"],
    "handshake": ["shakes hands with {target}", "offers {target} the official Oracle handshake", "seals the moment with {target} in a handshake"],
    "fistbump": ["fist-bumps {target}", "meets {target} with a quiet fist bump", "locks in a fist bump with {target}"],
    "shoulderpat": ["pats {target}'s shoulder", "gives {target} a reassuring shoulder pat", "rests a brief supportive pat on {target}'s shoulder"],
    "cheers": ["cheers with {target}", "raises an imaginary glass with {target}", "toasts {target} from the midnight corner"],
}
ACTION_MEDIA = {k: "anime " + k for k in ACTION_TEXT}

async def _members(chat_id: int) -> list[dict[str, Any]]:
    """Use the canonical persistent social registry, not a disconnected local counter."""
    members = await social_engine._members(chat_id)
    normalized = []
    for m in members:
        if not isinstance(m, dict):
            continue
        try:
            uid = int(m.get("id", 0))
        except (TypeError, ValueError):
            continue
        if uid <= 0 or m.get("is_bot", False):
            continue
        msgs = max(0, int(m.get("msgs", 0) or 0))
        normalized.append({
            "id": uid,
            "name": str(m.get("name") or "someone"),
            "username": str(m.get("username") or ""),
            "activity_score": min(1.0, msgs / 20.0),
            "is_bot": False,
        })
    return normalized

def _member_from_user(user) -> dict[str, Any]:
    return {"id": int(user.id), "name": user.first_name or "someone", "activity_score": 0.5, "is_bot": bool(user.is_bot), "username": user.username or ""}

async def _pair(update, context, kind):
    message, chat = update.effective_message, update.effective_chat
    if not message or not chat:
        return None
    if message.reply_to_message and message.reply_to_message.from_user:
        actor, target = update.effective_user, message.reply_to_message.from_user
        if actor and actor.id != target.id:
            return _member_from_user(actor), _member_from_user(target)
    members = await _members(chat.id)
    return choose_pair(context.application, chat.id, members, kind=kind)

async def _single_target(update, context, kind, allow_self=False):
    message, chat, actor = update.effective_message, update.effective_chat, update.effective_user
    if not message or not chat:
        return None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if allow_self or not actor or target.id != actor.id:
            return _member_from_user(target)
    members = await _members(chat.id)
    if not allow_self and actor:
        members = [m for m in members if m["id"] != actor.id]
    return choose_one(context.application, chat.id, members, kind=kind)

def _fresh(application, chat_id, kind, text, *, theme="social", pair="", media="", strategy="") -> str:
    governor = FreshnessGovernor(application)
    if governor.accept(chat_id, kind, text, theme=theme, media=media, pair=pair, strategy=strategy):
        return text
    # A second composition is deliberately different in structure, not merely punctuation.
    return text + "\n\n☾ The Oracle noticed this moment differently this time."

async def ship(update, context):
    pair = await _pair(update, context, "ship")
    if not pair:
        return await update.effective_message.reply_text("☾ I need at least two known members before Oracle can choose the pair.")
    a, b = pair; score = random.SystemRandom().randint(0, 100); tier = "low" if score < 40 else "mid" if score < 75 else "high"
    text = f"🚢 {mention(a['id'], a['name'])} + {mention(b['id'], b['name'])}\n\nShip name: *{_ship_name(a['name'], b['name'])}*\n{'❤️' * (score // 10)}{'🖤' * (10 - score // 10)} {score}%\n_{random.choice(SHIP_VERDICTS[tier])}_"
    await update.effective_message.reply_text(_fresh(context.application, update.effective_chat.id, "ship", text, pair=f"{a['id']}:{b['id']}", strategy=explain_lens("ship", context.application, update.effective_chat.id)), parse_mode="Markdown")

async def random_ship(update, context):
    pair = await _pair(update, context, "randomship")
    if not pair:
        return await update.effective_message.reply_text("☾ Not enough known members yet — let the room breathe a little first.")
    a, b = pair
    text = f"🎲 {mention(a['id'], a['name'])} + {mention(b['id'], b['name'])}\n\n*{random.SystemRandom().randint(0, 100)}%* match\n\n_The pairing was chosen by Oracle Instinct._"
    await update.effective_message.reply_text(_fresh(context.application, update.effective_chat.id, "randomship", text, pair=f"{a['id']}:{b['id']}", strategy=explain_lens("randomship", context.application, update.effective_chat.id)), parse_mode="Markdown")

async def track_message(update, context):
    if not update.effective_chat or not update.effective_user:
        return
    chat_id = update.effective_chat.id; user = update.effective_user
    entry = message_counts.setdefault(chat_id, {}).setdefault(user.id, {"name": user.first_name or "someone", "count": 0, "is_bot": bool(user.is_bot)})
    entry["name"] = user.first_name or entry.get("name") or "someone"; entry["count"] = int(entry.get("count", 0)) + 1

async def bestie(update, context):
    pair = await _pair(update, context, "bestie")
    if not pair: return await update.effective_message.reply_text("☾ I need two known members before Oracle can choose the bestie bond.")
    u1, u2 = pair; chat_id = update.effective_chat.id
    class Person:
        def __init__(self, d): self.id = d["id"]; self.first_name = d["name"]
    p1, p2 = Person(u1), Person(u2); declared_besties.setdefault(chat_id, {})[p1.id] = p2; declared_besties[chat_id][p2.id] = p1
    await update.effective_message.reply_text(_fresh(context.application, chat_id, "bestie", f"💛 {mention(p1.id, p1.first_name)} & {mention(p2.id, p2.first_name)}\n\n*BESTIE BOND SELECTED*\n\nThe Oracle put these two on the same side of the midnight table.", pair=f"{u1['id']}:{u2['id']}"), parse_mode="Markdown")

async def duo(update, context):
    pair = await _pair(update, context, "duo")
    if not pair: return await update.effective_message.reply_text("☾ I need two known members before I can forge a duo.")
    a, b = pair; label = f"{random.SystemRandom().choice(DUO_PREFIXES)} {random.SystemRandom().choice(DUO_SUFFIXES)}"
    await update.effective_message.reply_text(_fresh(context.application, update.effective_chat.id, "duo", f"🔗 {mention(a['id'], a['name'])} + {mention(b['id'], b['name'])}\n\n*{label}*\n\nTwo names. One completely unplanned team.", pair=f"{a['id']}:{b['id']}"), parse_mode="Markdown")

async def friendship_score(update, context):
    pair = await _pair(update, context, "friendship")
    if not pair: return await update.effective_message.reply_text("☾ I need two known members before Oracle can read the friendship.")
    a, b = pair; score = random.SystemRandom().randint(40, 100)
    await update.effective_message.reply_text(_fresh(context.application, update.effective_chat.id, "friendship", f"💫 *FRIENDSHIP SIGNAL*\n\n{mention(a['id'], a['name'])} × {mention(b['id'], b['name'])}\n\nSignal: *{score}%*\n\n_The number is playful. The choice is Oracle's._", pair=f"{a['id']}:{b['id']}"), parse_mode="Markdown")

async def tag_bestie(update, context):
    actor = update.effective_user; b = declared_besties.get(update.effective_chat.id, {}).get(actor.id if actor else 0)
    if not b: return await update.effective_message.reply_text("☾ No declared bestie yet — /bestie lets Oracle choose one.")
    await update.effective_message.reply_text(f"📣 {mention(actor.id, actor.first_name)} is calling {mention(b.id, b.first_name)}", parse_mode="Markdown")

async def squad(update, context):
    members = await _members(update.effective_chat.id)
    if not members: return await update.effective_message.reply_text("☾ Not enough activity data yet.")
    # Squad is intentionally not a top-message leaderboard: choose a varied group.
    chosen = []
    pool = members[:]
    rng = random.SystemRandom()
    while pool and len(chosen) < min(4, len(pool)):
        weights = [1.0 / (1.0 + len(chosen) * 0.25) for _ in pool]
        pick = rng.choices(pool, weights=weights, k=1)[0]; chosen.append(pick); pool.remove(pick)
    await update.effective_message.reply_text("👥 *ORACLE SQUAD*\n\n" + ", ".join(mention(m["id"], m["name"]) for m in chosen), parse_mode="Markdown")

async def loyalty(update, context):
    target = await _single_target(update, context, "loyalty", allow_self=True)
    if not target: return await update.effective_message.reply_text("☾ I need a known member before I can read loyalty.")
    await update.effective_message.reply_text(f"🛡️ {mention(target['id'], target['name'])}'s loyalty signal: *{random.SystemRandom().randint(60, 100)}/100*", parse_mode="Markdown")

async def matchmaker(update, context): await random_ship(update, context)
async def friendship_test(update, context): await friendship_score(update, context)

async def _action(update, context, key):
    target = await _single_target(update, context, key)
    if not target: return await update.effective_message.reply_text(f"☾ I need another known member before Oracle can choose someone for /{key}.")
    actor = update.effective_user
    actor_name = mention(actor.id, actor.first_name) if actor else "☾ Oracle"
    phrase = random.SystemRandom().choice(ACTION_TEXT[key]).format(target=mention(target['id'], target['name']))
    text = f"{actor_name} {phrase}."
    try:
        from handlers.chat import send_text_with_gif
        await send_text_with_gif(context.bot, update.effective_chat.id, text, ACTION_MEDIA[key])
    except Exception:
        await update.effective_message.reply_text(text, parse_mode="Markdown")

def _make_action(key):
    async def handler(update, context): await _action(update, context, key)
    handler.__name__ = key
    return handler

for _key in ACTION_TEXT:
    if _key not in globals(): globals()[_key] = _make_action(_key)

from handlers.fun import roast

def _ship_name(a: str, b: str) -> str:
    return (a[:max(1, len(a) // 2)] + b[len(b) // 2:]).title()
