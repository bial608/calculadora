"""
audit — a durable record of everything ATLAS did.

core/activity.py is the in-RAM journal (lost on restart). This subscribes to it
and writes two durable copies, cheaply and off the hot path:

    memory/audit/<date>.jsonl        one JSON line per event — for replay/export
    <vault>/ATLAS/Auditoria/<date>.md   a readable timeline, if a vault exists

Nothing here is on a tool's critical path: events are queued and flushed by a
background thread, so a slow disk or a missing vault never slows an action.
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

_q: queue.Queue = queue.Queue(maxsize=2000)
_started = False
_lock = threading.Lock()

_LABEL = {"tool": "🔧", "task": "🎯", "agent_step": "·", "conversa": "💬",
          "skill": "📘", "guard": "🛡️", "learn": "🧠", "error": "⚠️"}


def _base() -> Path:
    # Per-account when logged in (see memory/config_manager.get_base_dir), else
    # the install root — so each account keeps its own audit trail.
    try:
        from core import profile
        return profile.base_dir()
    except Exception:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent.parent


def _jsonl_path(d: datetime) -> Path:
    p = _base() / "memory" / "audit"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{d:%Y-%m-%d}.jsonl"


def _md_path(d: datetime) -> Path | None:
    try:
        from plugins import obsidian_brain as ob
        if ob._ensure_vault():
            p = ob.S.vault / ob.S.folder / "Auditoria"
            p.mkdir(parents=True, exist_ok=True)
            return p / f"{d:%Y-%m-%d}.md"
    except Exception:
        pass
    return None


def start() -> None:
    """Begin recording. Safe to call more than once."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    try:
        from core import activity
        activity.subscribe(_on_event)
    except Exception:
        return
    threading.Thread(target=_loop, daemon=True, name="audit").start()


def _on_event(evt: dict) -> None:
    try:
        _q.put_nowait(evt)
    except queue.Full:
        pass


def _loop() -> None:
    seen_md_header: set[str] = set()
    while True:
        evt = _q.get()
        if evt is None:
            continue
        try:
            now = datetime.fromtimestamp(evt.get("t", time.time()))
            rec = {"ts": now.isoformat(timespec="seconds"),
                   "kind": evt.get("kind"), "text": evt.get("text", ""),
                   **{k: v for k, v in evt.items() if k not in ("t", "kind", "text")}}
            with open(_jsonl_path(now), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            md = _md_path(now)
            if md is not None:
                hdr = md.name
                if hdr not in seen_md_header and not md.exists():
                    md.write_text(f"---\nsource: atlas\ntype: auditoria\ntags: [atlas, auditoria]\n---\n"
                                  f"# Auditoria {now:%d/%m/%Y}\n\n", encoding="utf-8")
                seen_md_header.add(hdr)
                icon = _LABEL.get(evt.get("kind"), "•")
                with open(md, "a", encoding="utf-8") as f:
                    f.write(f"- `{now:%H:%M:%S}` {icon} {str(evt.get('text',''))[:300]}\n")
        except Exception:
            continue


def recent(limit: int = 30, day: datetime | None = None) -> list[dict]:
    """Read back the day's events (for the '/audit' view and replay)."""
    day = day or datetime.now()
    out = []
    try:
        for line in _jsonl_path(day).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return out[-limit:]


def export(day: datetime | None = None) -> str:
    """A plain-text digest of a day, for the weekly review."""
    evts = recent(limit=10000, day=day)
    lines = [f"{e['ts'][11:19]}  {e.get('kind',''):10} {e.get('text','')}" for e in evts]
    return "\n".join(lines)
