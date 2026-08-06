"""
Shared helper for creating tappable @mentions.
Uses tg://user?id= links, which work even for users who haven't set a
username — more reliable than relying on @username text.
"""


def mention(user_id: int, name: str) -> str:
    """Returns Markdown-formatted clickable mention. Use with parse_mode='Markdown'."""
    escaped = name.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
    return f"[{escaped}](tg://user?id={user_id})"
