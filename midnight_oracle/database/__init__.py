"""Compatibility database facade for Midnight Oracle.

The repository contains a legacy async SQLite database module alongside the newer
SQLAlchemy model package. Existing engines use the async Database contract, so
this package re-exports that canonical implementation without duplicating it.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from .models import Base, Conversation, GroupMemory, OracleProphecy, RitualLog, User

_legacy_path = Path(__file__).resolve().parent.parent / "database.py"
_spec = importlib.util.spec_from_file_location("midnight_oracle._legacy_database", _legacy_path)
if _spec is None or _spec.loader is None:
    raise ImportError("Unable to load Midnight Oracle async database implementation")
_legacy = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _legacy
_spec.loader.exec_module(_legacy)
Database = _legacy.Database
now_ts = _legacy.now_ts

__all__ = ["Base", "Conversation", "GroupMemory", "OracleProphecy", "RitualLog", "User", "Database", "now_ts"]
