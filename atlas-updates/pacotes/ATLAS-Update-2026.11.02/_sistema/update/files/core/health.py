"""
health — is each piece alive? A tiny registry so one broken component is
visible and isolated, instead of silently taking the rest down.

Each background service / integration reports in:

    from core import health
    health.ok("obsidian")                 # healthy
    health.fail("gmail", "sem token")     # degraded, with a reason
    health.beat("wake")                   # still alive (heartbeat)

`report()` returns the current picture for the Dev Console ('/health'). The
registry never raises and holds no locks on the caller's hot path beyond a
cheap dict write.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_state: dict[str, dict] = {}


def _set(name: str, status: str, reason: str = "") -> None:
    with _lock:
        _state[name] = {"status": status, "reason": reason, "at": time.time()}


def ok(name: str) -> None:
    _set(name, "ok")


def fail(name: str, reason: str = "") -> None:
    _set(name, "fail", reason)
    try:
        from core import activity
        activity.record("error", f"{name} com problema: {reason}")
    except Exception:
        pass


def beat(name: str) -> None:
    _set(name, "ok")


def guarded(name: str, fn, *a, **kw):
    """Run fn; mark the component ok on success, fail (with the error) on
    exception — and swallow the exception so one component can't crash another."""
    try:
        r = fn(*a, **kw)
        ok(name)
        return r
    except Exception as e:
        fail(name, f"{type(e).__name__}: {e}")
        return None


def report() -> list[dict]:
    with _lock:
        now = time.time()
        return [{"name": n, "status": v["status"], "reason": v["reason"],
                 "ago": int(now - v["at"])}
                for n, v in sorted(_state.items())]


def summary() -> str:
    rows = report()
    if not rows:
        return "nada registrado ainda"
    bad = [r for r in rows if r["status"] != "ok"]
    if not bad:
        return f"tudo ok ({len(rows)} componentes)"
    return "problemas: " + ", ".join(f"{r['name']} ({r['reason'][:40]})" for r in bad)
