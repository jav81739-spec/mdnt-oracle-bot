"""Validated runtime configuration for Midnight Oracle.

All secrets are read from the environment (with .env support). No secret is
stored in source control. The module exposes one canonical configuration
surface plus backwards-compatible aliases used by the runtime modules.
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
        raise ConfigurationError(
            "DATABASE_URL must be a SQLAlchemy SQLite URL such as sqlite:///oracle.db"
        )
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
    telegram_token = _required("TELEGRAM_BOT_TOKEN")
    openai_key = _required("OPENAI_API_KEY")
    giphy_key = _required("GIPHY_API_KEY")
    sticker_pack = _required("STICKER_PACK_NAME")
    master_id = _int_env("ORACLE_MASTER_ID")
    database = _database_url(_required("DATABASE_URL"))
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


settings = load_settings()

TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
OPENAI_API_KEY = settings.openai_api_key
GIPHY_API_KEY = settings.giphy_api_key
STICKER_PACK_NAME = settings.sticker_pack_name
ORACLE_MASTER_ID = settings.oracle_master_id
DATABASE_URL = settings.database_url
LOG_LEVEL = settings.log_level
OPENAI_MODEL = settings.openai_model
TIMEZONE_NAME = settings.timezone_name
TIMEZONE = settings.timezone
OPENAI_TIMEOUT_SECONDS = settings.openai_timeout_seconds
MAX_OPENAI_RETRIES = settings.max_openai_retries
DM_HOURLY_LIMIT = settings.dm_hourly_limit
DM_SOFT_LIMIT = settings.dm_soft_limit
GROUP_HOURLY_LIMIT = settings.group_hourly_limit
GIF_MESSAGE_INTERVAL = settings.gif_message_interval
RANDOM_STICKER_PROBABILITY = settings.random_sticker_probability

# Compatibility names retained for the canonical runtime.  These aliases do
# not create a second configuration source; they point at the validated values
# above and prevent legacy imports from breaking the application.
BOT_TOKEN = TELEGRAM_BOT_TOKEN
DATABASE_PATH = DATABASE_URL

MOOD_STATES = (
    "MYSTICAL",
    "PROPHETIC",
    "PLAYFUL",
    "TENDER",
    "SHARP",
    "DARK_HUMOR",
    "SILENT_WISE",
    "STORM",
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
