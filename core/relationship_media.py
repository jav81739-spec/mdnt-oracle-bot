"""Original visual companion for Midnight Oracle relationship commands."""
from __future__ import annotations

from io import BytesIO
import hashlib
import re

from PIL import Image, ImageDraw, ImageFont


_MOODS = {
    "bond": ((38, 52, 64), (225, 205, 142)),
    "thread": ((34, 50, 59), (170, 206, 214)),
    "orbit": ((29, 43, 63), (180, 194, 228)),
    "echo": ((43, 43, 56), (207, 184, 224)),
    "tether": ((35, 52, 54), (191, 213, 179)),
    "rift": ((52, 39, 45), (222, 160, 160)),
    "spark": ((51, 45, 34), (240, 198, 115)),
    "mirror": ((36, 43, 54), (191, 211, 230)),
    "crossing": ((38, 48, 61), (191, 207, 226)),
    "undertow": ((31, 47, 55), (164, 199, 205)),
    "verdict": ((45, 43, 49), (224, 205, 166)),
    "watch": ((33, 48, 48), (186, 213, 197)),
    "unwatch": ((48, 46, 43), (203, 193, 170)),
    "sealed": ((43, 38, 51), (211, 191, 225)),
}

_ALIASES = {
    "weave": "thread",
    "anchor": "tether",
    "fracture": "rift",
    "ember": "spark",
    "edict": "verdict",
    "gaze": "watch",
    "release": "unwatch",
    "veil": "sealed",
}


def _stable_int(*values: object) -> int:
    raw = "|".join(str(value or "") for value in values).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _phrase(body: str, kind: str) -> str:
    """Pull a short, natural fragment from the actual generated reading."""
    text = " ".join(str(body or "").split()).strip()
    sentences = [part.strip(" \"'“”‘’") for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        return "A detail worth keeping in view."
    sentence = sentences[_stable_int(kind, text) % len(sentences)]
    words = sentence.split()
    if len(sentence) <= 58:
        return sentence
    if len(words) <= 9:
        return sentence[:58].rstrip(" ,;:") + "…"
    span = 7 + (_stable_int("span", kind, text) % 3)
    start = _stable_int("start", kind, text) % max(1, len(words) - span + 1)
    fragment = " ".join(words[start:start + span]).strip(" ,;:")
    return (fragment[:58].rstrip(" ,;:") + "…") if len(fragment) >= 58 else fragment + "…"


def build_relationship_gif(body: str, kind: str) -> BytesIO:
    """Build one original, command-specific GIF carrying a fragment of the reading."""
    kind = _ALIASES.get(kind, kind)
    background, accent = _MOODS.get(kind, _MOODS["bond"])
    phrase = _phrase(body, kind)
    width, height = 720, 360
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 38)
    small = ImageFont.truetype(font_path, 20)
    frames: list[Image.Image] = []
    for frame_index in range(6):
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        pulse = 8 + (frame_index if frame_index <= 3 else 6 - frame_index)
        draw.ellipse((54 - pulse, 54 - pulse, 118 + pulse, 118 + pulse), fill=accent)
        draw.ellipse((78 - pulse // 2, 47 - pulse // 2, 128 + pulse // 2, 98 + pulse // 2), fill=background)
        stars = ((180, 70), (590, 82), (640, 260), (100, 285), (530, 55))
        for x, y in stars:
            radius = 2 + ((_stable_int(kind, frame_index, x, y) % 3))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(220, 224, 228))
        bbox = draw.multiline_textbbox((0, 0), phrase, font=font, spacing=8, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (width - tw) / 2
        y = 150 + (2 if frame_index in (1, 2, 4) else 0)
        draw.rounded_rectangle(
            (x - 28, y - 22, x + tw + 28, y + th + 22),
            radius=24,
            fill=(29, 40, 52),
            outline=accent,
            width=2,
        )
        draw.multiline_text((x, y), phrase, font=font, fill=(246, 247, 244), spacing=8, align="center")
        draw.text((width - 180, height - 44), "— Midnight Oracle", font=small, fill=(170, 178, 188))
        frames.append(image)
    output = BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=130, loop=0, optimize=True)
    output.name = f"midnight-oracle-{kind}.gif"
    output.seek(0)
    return output
