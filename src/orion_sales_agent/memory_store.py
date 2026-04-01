"""Persistence helpers for lightweight bounded agent conversation memory."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


def load_memory(memory_file: Path) -> list[dict[str, Any]]:
    """Load persisted memory records.

    Returns an empty list when the file is missing or malformed.
    """

    if not memory_file.exists():
        return []
    try:
        return cast(list[dict[str, Any]], json.loads(memory_file.read_text(encoding="utf-8")))
    except Exception as exc:
        logger.warning("Memory file '%s' could not be parsed, starting fresh: %s", memory_file, exc)
        return []


_MAX_MEMORY_BYTES: int = 50_000  # 50 KB hard cap to prevent unbounded disk growth


def save_memory(memory_file: Path, items: list[dict[str, Any]], max_items: int = 20) -> None:
    """Persist the trailing bounded memory window to disk.

    Enforces two limits:
    - At most *max_items* records (removes oldest first).
    - At most ``_MAX_MEMORY_BYTES`` bytes serialised; if the trailing window
      still exceeds the cap, items are dropped from the front until it fits.
    """

    memory_file.parent.mkdir(parents=True, exist_ok=True)
    window = list(items[-max_items:])
    # Byte-size guard: trim from the front until serialised size is within cap.
    while window:
        serialised = json.dumps(window, indent=2)
        if len(serialised.encode()) <= _MAX_MEMORY_BYTES:
            break
        window.pop(0)
    memory_file.write_text(
        json.dumps(window, indent=2) if window else "[]", encoding="utf-8"
    )
