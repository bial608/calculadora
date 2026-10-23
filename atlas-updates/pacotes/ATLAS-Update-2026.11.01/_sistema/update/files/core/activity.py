"""
What ATLAS did — a tiny in-process journal.

main.py records every tool call, the task agent records every step and every
finished task. Anything can subscribe (obsidian_brain uses it for the BLUE
"what I did" part of each screenshot entry) or read what happened since a
moment in time. Kept in memory only, capped, thread-safe; nothing is written to
disk here.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

_events: deque = deque(maxlen=500)
_lock = threading.Lock()
_subs: list[Callable[[dict], None]] = []

# Tool calls that are bookkeeping, not something the user would call "doing".
QUIET_TOOLS = {"save_memory", "recall_memory", "obsidian_brain", "ask_9router",
               "system_status"}


def record(kind: str, text: str, **extra) -> None:
    evt = {"t": time.time(), "kind": kind, "text": str(text)[:400], **extra}
    with _lock:
        _events.append(evt)
    for fn in list(_subs):
        try:
            fn(evt)
        except Exception:
            pass


def subscribe(fn: Callable[[dict], None]) -> None:
    if fn not in _subs:
        _subs.append(fn)


def since(t0: float) -> list[dict]:
    with _lock:
        return [e for e in _events if e["t"] >= t0]
