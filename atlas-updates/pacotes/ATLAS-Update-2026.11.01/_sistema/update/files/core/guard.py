"""
guard — the brake pedal. One place that decides whether a risky action may run.

Every action that changes something outside ATLAS (send a message, delete or
overwrite files, pay, type a password, run a brand-new learned skill) asks
`check()` BEFORE doing it. The guard answers allow / confirm / block:

    allow    — go ahead
    confirm  — a human must press the confirmation button first
    block    — refused right now (kill switch on, or rate limit hit)

It also holds the KILL SWITCH: one flag that, while set, blocks every risky
action and stops the autonomous agent. Flipping it is instant and global.

Design: pure, in-process, no I/O on the hot path, thread-safe. Nothing here
talks to a model or the network, so it cannot itself be slow or fail open.
"""
from __future__ import annotations

import threading
import time

# ── Kill switch ───────────────────────────────────────────────────────────────
_killed = threading.Event()
_lock = threading.Lock()

# Rolling window of destructive actions, for the rate limit.
_recent: list[float] = []

# Defaults; the Recursos panel overrides these via configure().
_cfg = {
    "enabled": True,          # master: when False, guard always allows (not advised)
    "max_destructive_per_hour": 30,
    "confirm_payment": True,
    "confirm_password": True,
    "confirm_delete_over": 5,     # deleting more than N files needs confirmation
    "confirm_send_others": True,  # sending anything to other people
    "dry_run_new_skills": True,
}

# What counts as destructive (rate-limited + often confirmed).
DESTRUCTIVE = {"delete", "overwrite", "move", "send_message", "pay", "purchase",
               "shutdown", "restart", "wifi", "close_app"}


def configure(values: dict) -> None:
    with _lock:
        _cfg.update({k: v for k, v in (values or {}).items() if k in _cfg})


def settings() -> dict:
    with _lock:
        return dict(_cfg)


# ── Kill switch API ─────────────────────────────────────────────────────────
def kill(reason: str = "") -> None:
    """Stop everything risky now. Also stops the running task agent."""
    _killed.set()
    try:
        from actions import task_agent
        task_agent.stop()
    except Exception:
        pass
    try:
        from core import activity
        activity.record("guard", f"KILL SWITCH acionado{(' — ' + reason) if reason else ''}")
    except Exception:
        pass


def release() -> None:
    _killed.clear()
    try:
        from core import activity
        activity.record("guard", "kill switch liberado")
    except Exception:
        pass


def is_killed() -> bool:
    return _killed.is_set()


# ── The gate ──────────────────────────────────────────────────────────────────
def _rate_ok(now: float, limit: int) -> bool:
    cutoff = now - 3600
    with _lock:
        _recent[:] = [t for t in _recent if t >= cutoff]
        return len(_recent) < limit


def note_destructive() -> None:
    """Record that a destructive action actually ran (feeds the rate limit)."""
    with _lock:
        _recent.append(time.monotonic())


def check(kind: str, *, count: int = 1, to_others: bool = False,
          new_skill: bool = False) -> tuple[str, str]:
    """Decide whether an action may run.

    kind: a word from DESTRUCTIVE, or any label for a benign action.
    Returns (verdict, reason) where verdict is 'allow' | 'confirm' | 'block'.
    """
    cfg = settings()
    if is_killed():
        return "block", "o kill switch está acionado — nada que altere o sistema roda até você liberar"
    if not cfg.get("enabled", True):
        return "allow", ""

    kind = (kind or "").lower()
    destructive = kind in DESTRUCTIVE

    if destructive and not _rate_ok(time.monotonic(), int(cfg.get("max_destructive_per_hour", 30))):
        return "block", (f"limite de {cfg['max_destructive_per_hour']} ações que alteram o "
                         f"sistema por hora atingido — espere ou aumente no painel Recursos")

    # Things that always need a human finger.
    if kind in ("pay", "purchase") and cfg.get("confirm_payment", True):
        return "confirm", "pagamento precisa da sua confirmação"
    if kind == "password" and cfg.get("confirm_password", True):
        return "confirm", "digitar senha precisa da sua confirmação"
    if kind in ("delete", "overwrite") and count > int(cfg.get("confirm_delete_over", 5)):
        return "confirm", f"apagar/sobrescrever {count} arquivos precisa da sua confirmação"
    if to_others and cfg.get("confirm_send_others", True):
        return "confirm", "enviar algo para outra pessoa precisa da sua confirmação"
    if new_skill and cfg.get("dry_run_new_skills", True):
        return "confirm", "é uma tarefa nova — confirme para eu executar de verdade (dry-run)"

    return "allow", ""


def guard_destructive(kind: str, **kw) -> tuple[bool, str]:
    """Convenience for a non-interactive action: True to proceed. When the
    verdict is 'confirm' here (no UI to ask), it is treated as 'needs you' and
    returns False with the reason, which the caller speaks."""
    verdict, reason = check(kind, **kw)
    if verdict == "allow":
        note_destructive()
        return True, ""
    return False, reason
