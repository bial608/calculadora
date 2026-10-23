"""
accounts — local login for ATLAS (nickname + password).

Accounts are shared across profiles and stored at <install>/config/users.json.
Passwords are never kept in plain text: each is a PBKDF2-HMAC-SHA256 hash with a
per-user random salt.

There is one built-in admin (nickname "admin", password "bialrubi"). The admin
password lives in this source file, so treat it as a CONVENIENCE GATE, not real
security: anyone with the ATLAS files can read it. The admin can browse and
switch into any LOCAL profile on this computer (see the admin panel) — it is not
access to anyone else's machine.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from core import profile

ADMIN_NAME = "admin"
_ADMIN_PASSWORD = "bialrubi"      # convenience gate only — see module docstring
_ITERATIONS = 120_000


def _users_file() -> Path:
    return profile.install_root() / "config" / "users.json"


def _load() -> dict:
    try:
        return json.loads(_users_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    f = _users_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                               _ITERATIONS).hex()


def _norm(nick: str) -> str:
    return (nick or "").strip()


def exists(nick: str) -> bool:
    nick = _norm(nick)
    return nick.lower() == ADMIN_NAME or nick in _load()


def is_admin(nick: str) -> bool:
    return _norm(nick).lower() == ADMIN_NAME


def register(nick: str, password: str) -> tuple[bool, str]:
    nick = _norm(nick)
    if not nick or len(nick) < 2:
        return False, "Escolha um nickname com pelo menos 2 letras."
    if nick.lower() == ADMIN_NAME:
        return False, "Esse nome é reservado."
    if not password or len(password) < 3:
        return False, "A senha precisa de pelo menos 3 caracteres."
    data = _load()
    if nick in data:
        return False, "Esse nickname já existe — faça login."
    salt = os.urandom(16)
    data[nick] = {"salt": salt.hex(), "hash": _hash(password, salt),
                  "created": time.strftime("%Y-%m-%d %H:%M"), "admin": False}
    _save(data)
    return True, "Conta criada."


def verify(nick: str, password: str) -> tuple[bool, bool, str]:
    """-> (ok, is_admin, message)."""
    nick = _norm(nick)
    if nick.lower() == ADMIN_NAME:
        if password == _ADMIN_PASSWORD:
            return True, True, "Bem-vindo, admin."
        return False, False, "Senha do admin incorreta."
    rec = _load().get(nick)
    if not rec:
        return False, False, "Conta não encontrada — registre-se."
    try:
        ok = _hash(password, bytes.fromhex(rec["salt"])) == rec["hash"]
    except Exception:
        ok = False
    return (True, False, "Login ok.") if ok else (False, False, "Senha incorreta.")


def list_users() -> list[dict]:
    """Every known account (admin first), for the admin panel. No secrets."""
    out = [{"nick": ADMIN_NAME, "admin": True, "created": "(embutido)"}]
    for nick, rec in sorted(_load().items()):
        out.append({"nick": nick, "admin": bool(rec.get("admin")),
                    "created": rec.get("created", "")})
    return out


def delete(nick: str) -> bool:
    nick = _norm(nick)
    if nick.lower() == ADMIN_NAME:
        return False
    data = _load()
    if nick in data:
        data.pop(nick)
        _save(data)
        return True
    return False
