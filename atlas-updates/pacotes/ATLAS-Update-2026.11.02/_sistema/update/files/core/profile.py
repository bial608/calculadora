"""
profile — which account's data this run uses.

ATLAS can hold several local accounts on one machine. Each account's settings,
memory, skills and audit live in their own folder:

    <install>/profiles/<nickname>/config/...
    <install>/profiles/<nickname>/memory/...

The active account is chosen at login (core/boot.py) and passed down through the
environment variable ATLAS_PROFILE, read HERE. Every module that stores data
builds its paths from `base_dir()`, so pointing this at a profile moves all of
that account's data at once — with no profile set, `base_dir()` is the install
root, exactly as before this existed.

Accounts are LOCAL to this computer. This is not remote access to anyone else's
machine; the admin account can browse only the profiles stored here.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def install_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def active() -> str:
    """The logged-in nickname, or '' when login was skipped (legacy/default)."""
    return (os.environ.get("ATLAS_PROFILE") or "").strip()


def profiles_root() -> Path:
    return install_root() / "profiles"


def base_dir() -> Path:
    """Where THIS run reads and writes its data. A profile dir when logged in,
    else the install root (unchanged behaviour)."""
    name = active()
    if not name:
        return install_root()
    d = profiles_root() / _safe(name)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def _safe(name: str) -> str:
    keep = "".join(c for c in str(name) if c.isalnum() or c in "-_ .")
    return (keep.strip() or "user")[:40]


def list_profiles() -> list[str]:
    r = profiles_root()
    if not r.is_dir():
        return []
    return sorted(p.name for p in r.iterdir() if p.is_dir())


def set_active(name: str) -> Path:
    """Make `name` the active profile for this process and return its dir.
    On first use, inherits the existing install-root config/memory so a user who
    already set ATLAS up does not lose it when login is turned on."""
    name = _safe(name)
    os.environ["ATLAS_PROFILE"] = name
    d = profiles_root() / name
    d.mkdir(parents=True, exist_ok=True)
    _migrate_legacy(d)
    return d


_MIGRATED = "profiles/.migrated"


def _migrate_legacy(dest: Path) -> None:
    """Copy the pre-login config + memory from the install root into the FIRST
    profile created, once. Later profiles start fresh."""
    marker = install_root() / _MIGRATED
    if marker.exists():
        return
    root = install_root()
    root_cfg = root / "config" / "api_keys.json"
    if not root_cfg.exists():
        return
    try:
        if not (dest / "config" / "api_keys.json").exists():
            for sub in ("config", "memory"):
                src = root / sub
                if src.is_dir():
                    shutil.copytree(src, dest / sub, dirs_exist_ok=True)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(dest.name, encoding="utf-8")
    except Exception:
        pass
