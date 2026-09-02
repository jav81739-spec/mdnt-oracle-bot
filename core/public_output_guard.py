"""Final public-output hygiene for Midnight Oracle expressive messages.

This guard does not generate content and does not inspect private conversations.
It only removes legacy language that can falsely imply surveillance, hidden
records, algorithmic selection, or an internal testing/debug state.
"""
from __future__ import annotations

import re

_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"the oracle has been watching (?P<x>.+?) for a while now\.", re.I),
     r"somehow, tonight's attention lands on \g<x>."),
    (re.compile(r"the oracle saved its voice all day for this\.", re.I),
     "some moments are worth waiting for."),
    (re.compile(r"midnight\. the oracle opens its eye\. it lands on (?P<x>.+?)\.", re.I),
     r"midnight lands here: \g<x>."),
    (re.compile(r"the oracle has read both (?P<x>.+?)\. this isn't new\. it's a continuation\.", re.I),
     r"there's something familiar in the space between \g<x>."),
    (re.compile(r"the oracle sees the full arc\.", re.I),
     "some connections take longer to make sense."),
    (re.compile(r"the oracle doesn't choose randomly\.\s*it chooses correctly\. always\.", re.I),
     "some pairings simply make sense tonight."),
    (re.compile(r"oracle-certified\. no further explanation\.?", re.I),
     "no explanation needed."),
    (re.compile(r"filed in the midnight archives\. permanent\. witnessed\.?", re.I),
     "some moments don't need a footnote."),
    (re.compile(r"the oracle has measured it\.", re.I),
     "you can feel the difference."),
    (re.compile(r"the oracle has spoken\.", re.I),
     "that's tonight's thought."),
    (re.compile(r"the oracle doesn't label what it sees\. it only reveals that it's real\.", re.I),
     "sometimes a moment speaks for itself."),
    (re.compile(r"the oracle is naming two people", re.I),
     "tonight, two names belong together"),
    (re.compile(r"the oracle hears both\.", re.I),
     "both sides of this feel different."),
    (re.compile(r"the oracle rarely finds this alignment\.\s*when it does — it pays attention\.", re.I),
     "rare alignments are worth noticing."),
    (re.compile(r"the oracle has been watching", re.I), "somehow, this stands out"),
    (re.compile(r"the oracle has read", re.I), "there's something interesting here"),
    (re.compile(r"the oracle has measured", re.I), "you can feel"),
    (re.compile(r"the oracle sees", re.I), "it feels like"),
    (re.compile(r"the oracle hears", re.I), "it feels like"),
    (re.compile(r"the oracle doesn't choose", re.I), "this isn't about choosing"),
    (re.compile(r"the oracle chooses", re.I), "tonight, it lands on"),
)

_FORBIDDEN_PUBLIC = re.compile(
    r"\b(?:testing message|test message|testing output|test output|debug message|"
    r"debug output|placeholder message|placeholder output)\b",
    re.I,
)


def clean_public_text(text: str) -> str:
    """Return expressive text safe for public Telegram delivery."""
    value = str(text or "")
    for pattern, replacement in _REPLACEMENTS:
        value = pattern.sub(replacement, value)
    value = _FORBIDDEN_PUBLIC.sub("", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def guard_post(post):
    """Wrap a Social Engine post function without changing its public API."""
    async def guarded(bot, chat_id, text):
        return await post(bot, chat_id, clean_public_text(text))
    guarded.__name__ = getattr(post, "__name__", "guarded_post")
    guarded.__doc__ = getattr(post, "__doc__", None)
    return guarded
