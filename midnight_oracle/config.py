"""Validated runtime configuration for Midnight Oracle.

Configuration is import-safe: importing modules for tests does not require
production secrets. Runtime startup remains strict through ``load_settings``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(override=False)


class ConfigurationError(RuntimeError):
    """Raised when required Midnight Oracle configuration is invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _optional(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _int_env(name: str, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        if default is None:
            raise ConfigurationError(f"Missing required integer environment variable: {name}")
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _database_url(raw: str) -> str:
    value = raw.strip()
    if value.startswith("sqlite:///"):
        return value
    if value.startswith("sqlite://"):
        raise ConfigurationError("DATABASE_URL must be a SQLAlchemy SQLite URL such as sqlite:///oracle.db")
    if "://" in value:
        raise ConfigurationError("Only SQLite DATABASE_URL values are supported by this build")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return f"sqlite:///{path.as_posix()}"


def _validate_token(name: str, value: str) -> None:
    if len(value) < 20:
        raise ConfigurationError(f"{name} appears too short to be a valid secret")


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    giphy_api_key: str
    sticker_pack_name: str
    oracle_master_id: int
    database_url: str
    log_level: str
    timezone_name: str
    openai_model: str = "gpt-4o"
    openai_timeout_seconds: float = 30.0
    max_openai_retries: int = 3
    dm_hourly_limit: int = 20
    dm_soft_limit: int = 15
    group_hourly_limit: int = 10
    gif_message_interval: int = 5
    random_sticker_probability: float = 0.08

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)


def load_settings() -> Settings:
    telegram_token = _optional("TELEGRAM_BOT_TOKEN") or _optional("BOT_TOKEN")
    if not telegram_token:
        raise ConfigurationError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
    openai_key = _required("OPENAI_API_KEY")
    giphy_key = _required("GIPHY_API_KEY")
    sticker_pack = _required("STICKER_PACK_NAME")
    master_id = _int_env("ORACLE_MASTER_ID")
    database_raw = _optional("DATABASE_URL") or _optional("DATABASE_PATH")
    if not database_raw:
        raise ConfigurationError("Missing required environment variable: DATABASE_URL")
    database = _database_url(database_raw)
    log_level = (_optional("LOG_LEVEL", "INFO") or "INFO").upper()
    if log_level not in {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("LOG_LEVEL must be a valid Loguru level")
    timezone_name = _optional("ORACLE_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata"
    try:
        ZoneInfo(timezone_name)
    except Exception as exc:
        raise ConfigurationError(f"Invalid ORACLE_TIMEZONE: {timezone_name}") from exc
    _validate_token("TELEGRAM_BOT_TOKEN", telegram_token)
    _validate_token("OPENAI_API_KEY", openai_key)
    _validate_token("GIPHY_API_KEY", giphy_key)
    if master_id <= 0:
        raise ConfigurationError("ORACLE_MASTER_ID must be a positive Telegram user ID")
    return Settings(
        telegram_bot_token=telegram_token,
        openai_api_key=openai_key,
        giphy_api_key=giphy_key,
        sticker_pack_name=sticker_pack,
        oracle_master_id=master_id,
        database_url=database,
        log_level=log_level,
        timezone_name=timezone_name,
        openai_model=_optional("OPENAI_MODEL", "gpt-4o") or "gpt-4o",
    )


# Import-safe compatibility surface. Required production validation happens
# when ``load_settings`` is called by the runtime entrypoint.
TELEGRAM_BOT_TOKEN = _optional("TELEGRAM_BOT_TOKEN") or _optional("BOT_TOKEN")
OPENAI_API_KEY = _optional("OPENAI_API_KEY")
GIPHY_API_KEY = _optional("GIPHY_API_KEY")
STICKER_PACK_NAME = _optional("STICKER_PACK_NAME")
ORACLE_MASTER_ID = _int_env("ORACLE_MASTER_ID", 0)
_DATABASE_RAW = _optional("DATABASE_URL") or _optional("DATABASE_PATH", "midnight_oracle.sqlite3")
DATABASE_URL = _database_url(_DATABASE_RAW)
LOG_LEVEL = (_optional("LOG_LEVEL", "INFO") or "INFO").upper()
OPENAI_MODEL = _optional("OPENAI_MODEL", "gpt-4o") or "gpt-4o"
TIMEZONE_NAME = _optional("ORACLE_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
OPENAI_TIMEOUT_SECONDS = 30.0
MAX_OPENAI_RETRIES = 3
DM_HOURLY_LIMIT = 20
DM_SOFT_LIMIT = 15
GROUP_HOURLY_LIMIT = 10
GIF_MESSAGE_INTERVAL = 5
RANDOM_STICKER_PROBABILITY = 0.08

BOT_TOKEN = TELEGRAM_BOT_TOKEN
DATABASE_PATH = DATABASE_URL

# Ambient conversation controls.
ENGAGEMENT_THRESHOLD = 6
AMBIENT_ENGAGEMENT_RATE = 0.30
PER_MEMBER_COOLDOWN_SECONDS = 600
PER_GROUP_COOLDOWN_SECONDS = 600
MAX_AMBIENT_REPLIES_PER_HOUR = 2
SERIOUS_CONVERSATION_COOLDOWN_SECONDS = 1200
SCHEDULED_MESSAGE_GAP_SECONDS = 14400
GROUP_RECENT_MESSAGE_LIMIT = 10
MOOD_WINDOW = 10

# Memory limits.
MEMORY_INTEREST_LIMIT = 10
MEMORY_THEME_LIMIT = 5
MEMORY_WORRY_LIMIT = 10
MEMORY_WIN_LIMIT = 10
MEMORY_JOKE_LIMIT = 10
MEMORY_RECENT_DAYS = 30

# Schedule and interaction constants.
MORNING_HOUR = 7
MORNING_MINUTE = 30
EVENING_HOUR = 20
EVENING_MINUTE = 0
LATE_NIGHT_START = 23
LATE_NIGHT_END = 3
THREE_AM_START = 0
THREE_AM_END = 3
JOKE_MAX_PER_GROUP = 20
JOKE_CALLBACK_PROBABILITY = 0.15
JOKE_CALLBACK_GAP_SECONDS = 172800
ABSENCE_DAYS = 5
ABSENCE_PING_GAP_DAYS = 14
ABSENCE_CHECK_HOUR = 14
MAX_STICKER_EVENTS_PER_HOUR = 3
SECRET_EVENT_MAX_WEEKLY = 2
MAX_ACHIEVEMENTS_PER_EVENT = 3
GAME_POLL_SECONDS = 60

# Oracle behaviour constants.
MOOD_STATES = (
    "MYSTICAL", "PROPHETIC", "PLAYFUL", "TENDER",
    "SHARP", "DARK_HUMOR", "SILENT_WISE", "STORM",
)
RECENT_MESSAGES_LIMIT = 20
SOUL_SNAPSHOT_WORD_LIMIT = 200
SOUL_SNAPSHOT_REFRESH_MESSAGES = 10
RITUAL_VISION_WORD_LIMIT = 300
SILENCE_SECONDS = 60 * 60
PROPHECY_MAX_PER_HOUR = 3
GROUP_AMBIENT_PROBABILITY = 0.03
GROUP_VIBE_KEYWORD_THRESHOLD = 5
WEEKLY_ACTIVE_DAYS = 7
MIDNIGHT_START_HOUR = 23
MIDNIGHT_END_HOUR = 2
DAWN_START_HOUR = 5
MORNING_START_HOUR = 8
AFTERNOON_START_HOUR = 12
DUSK_START_HOUR = 17
NIGHT_START_HOUR = 20
DEEP_NIGHT_START_HOUR = 2

FALLBACK_REPLIES = (
    "Haan. Suna. ☾",
    "Yahin hoon. Bolo.",
    "Hmm… midnight sun raha hai.",
    "Batao. Kya chal raha hai?",
    "haan, bolo. 🌙",
    "I’m listening. No rush.",
    "Achha… ab asli baat batao.",
    "Haan. I’m here.",
)
