"""Persistence helpers for lightweight bounded agent conversation memory."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_memory(memory_file: Path) -> list[dict[str, Any]]:
    """Load persisted memory records.

    Returns an empty list when the file is missing or malformed.
    """

    if not memory_file.exists():
        return []
    try:
        return json.loads(memory_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Memory file '%s' could not be parsed, starting fresh: %s", memory_file, exc)
        return []


def save_memory(memory_file: Path, items: list[dict[str, Any]], max_items: int = 20) -> None:
    """Persist the trailing bounded memory window to disk."""

    memory_file.parent.mkdir(parents=True, exist_ok=True)
    memory_file.write_text(json.dumps(items[-max_items:], indent=2), encoding="utf-8")
