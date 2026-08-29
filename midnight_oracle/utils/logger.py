"""Structured logging helpers."""
from __future__ import annotations
import logging


def get_logger(name: str) -> logging.Logger:
    """Return a consistently configured application logger."""
    return logging.getLogger(name)


def configure_logging() -> None:
    """Configure concise process-wide logging once."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
