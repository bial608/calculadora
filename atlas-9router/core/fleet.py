"""
fleet — control YOUR OTHER computers from the main one, even in other houses.

THE PROBLEM, HONESTLY
    SSH alone only reaches machines on the SAME local network. Two PCs in two
    different houses sit behind two different routers and cannot see each other
    over the internet on their own — no amount of "refresh every 5 minutes"
    changes that. Something has to join them across the internet first.

THE PRACTICAL, SAFE ANSWER: Tailscale
    Tailscale (https://tailscale.com, free for personal use) puts all YOUR
    machines on one private, encrypted network (WireGuard), wherever they are.
    Install it on each PC, sign in with the SAME account, and they can reach
    each other by a STABLE NAME (e.g. "pc-sala") — no IP to look up, no router
    to touch, no port to open. It is far simpler and safer than forwarding ports.

    So this module:
      • discovers your machines automatically by reading `tailscale status`
        (no IP, no typing — the panel refreshes this every 5 minutes);
      • detects THIS machine's Windows user by itself;
      • then controls a machine over SSH to its Tailscale name. With Tailscale
        SSH turned on, you don't even copy a key.

    ATLAS still runs no server of its own and stores no passwords: Tailscale
    carries the identity, SSH carries the session. Leaving the tailnet (or
    turning SSH off) removes access cleanly.

    A manually added machine (name·host·user) still works too, as a fallback for
    same-house machines without Tailscale.
"""
from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from core import profile

_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
             "-o", "StrictHostKeyChecking=accept-new"]


# ─────────────────────────────────────────────────────────────────────────────
#  This machine
# ─────────────────────────────────────────────────────────────────────────────
def local_user() -> str:
    """The Windows username of whoever is logged in here — so you never type it."""
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or ""


# ─────────────────────────────────────────────────────────────────────────────
#  Tailscale discovery (the automatic list)
# ─────────────────────────────────────────────────────────────────────────────
def tailscale_bin() -> str | None:
    p = shutil.which("tailscale")
    if p:
        return p
    for cand in (r"C:\Program Files\Tailscale\tailscale.exe",
                 r"C:\Program Files (x86)\Tailscale\tailscale.exe"):
        if os.path.exists(cand):
            return cand
    return None


def tailscale_available() -> bool:
    return tailscale_bin() is not None


def tailscale_devices() -> list[dict]:
    """Every machine on your tailnet, read from `tailscale status --json`.
    Returns [] if Tailscale isn't installed or isn't up yet."""
    b = tailscale_bin()
    if not b:
        return []
    try:
        r = subprocess.run([b, "status", "--json"], capture_output=True,
                           text=True, timeout=10)
        data = json.loads(r.stdout or "{}")
    except Exception:
        return []

    def node_to_dev(node: dict, is_self: bool) -> dict | None:
        if not node:
            return None
        name = node.get("HostName") or (node.get("DNSName", "").split(".")[0])
        if not name:
            return None
        dns = (node.get("DNSName") or "").rstrip(".")
        ips = node.get("TailscaleIPs") or []
        host = dns or (ips[0] if ips else name)
        return {"name": name, "host": host,
                "online": True if is_self else bool(node.get("Online")),
                "os": node.get("OS", ""), "is_self": is_self}

    devs = []
    self_dev = node_to_dev(data.get("Self") or {}, True)
    if self_dev:
        devs.append(self_dev)
    for node in (data.get("Peer") or {}).values():
        d = node_to_dev(node, False)
        if d:
            devs.append(d)
    # online first, then by name
    devs.sort(key=lambda d: (not d["online"], d["name"].lower()))
    return devs


# ─────────────────────────────────────────────────────────────────────────────
#  Manual list (fallback / per-machine overrides), stored in the admin profile
# ─────────────────────────────────────────────────────────────────────────────
def _file() -> Path:
    return profile.base_dir() / "config" / "fleet.json"


def load() -> list[dict]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(machines: list[dict]) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(machines, indent=2, ensure_ascii=False), encoding="utf-8")


def add(name: str, host: str, user: str, key_path: str = "") -> tuple[bool, str]:
    """Add a machine, or override the user/host/key for a discovered one
    (matched by name)."""
    name, host, user = name.strip(), host.strip(), user.strip()
    if not name or not host or not user:
        return False, "Preencha nome, host e usuário."
    machines = [m for m in load() if m.get("name", "").strip().lower() != name.lower()]
    machines.append({"name": name, "host": host, "user": user, "key_path": key_path.strip()})
    _save(machines)
    return True, f"Máquina '{name}' salva."


def set_user(name: str, user: str) -> bool:
    """Remember the Windows user for a (possibly discovered) machine, without
    making the person retype its host."""
    m = _machine_for(name)
    if not m:
        return False
    return add(m["name"], m["host"], user.strip() or local_user(), m.get("key_path", ""))[0]


def remove(name: str) -> bool:
    before = load()
    after = [m for m in before if m.get("name", "").strip().lower() != name.strip().lower()]
    if len(after) == len(before):
        return False
    _save(after)
    return True


def _manual(name_or_host: str) -> dict | None:
    key = (name_or_host or "").strip().lower()
    for m in load():
        if m.get("name", "").strip().lower() == key or m.get("host", "").strip().lower() == key:
            return m
    return None


# kept for compatibility — the manual entry for a name, if any
def get(name: str) -> dict | None:
    return _manual(name)


# ─────────────────────────────────────────────────────────────────────────────
#  The merged view everything else uses
# ─────────────────────────────────────────────────────────────────────────────
def discover() -> list[dict]:
    """Tailscale machines (auto) + manually added ones, merged. Each entry has
    name · host · user · online · os · source."""
    out: list[dict] = []
    seen: set[str] = set()
    me = local_user()
    for d in tailscale_devices():
        ov = _manual(d["name"]) or _manual(d["host"])
        out.append({"name": d["name"], "host": ov["host"] if ov else d["host"],
                    "user": (ov or {}).get("user") or me,
                    "key_path": (ov or {}).get("key_path", ""),
                    "online": d["online"], "os": d["os"],
                    "is_self": d["is_self"], "source": "tailscale"})
        seen.add(d["name"].lower())
    for m in load():
        if m.get("name", "").strip().lower() in seen:
            continue
        out.append({"name": m["name"], "host": m["host"], "user": m.get("user") or me,
                    "key_path": m.get("key_path", ""), "online": None, "os": "",
                    "is_self": False, "source": "manual"})
    return out


def _machine_for(name_or_host: str) -> dict | None:
    key = (name_or_host or "").strip().lower()
    for d in discover():
        if d["name"].lower() == key or d["host"].lower() == key:
            return d
    # last resort: a manual entry not in discover() (shouldn't happen)
    return _manual(name_or_host)


# ─────────────────────────────────────────────────────────────────────────────
#  Control (SSH / SCP / RDP), by machine NAME only
# ─────────────────────────────────────────────────────────────────────────────
def _target(m: dict) -> str:
    return f"{m['user']}@{m['host']}"


def _ssh_cmd(m: dict, remote_command: str) -> list[str]:
    cmd = ["ssh", *_SSH_OPTS]
    if m.get("key_path"):
        cmd += ["-i", m["key_path"]]
    cmd += [_target(m), remote_command]
    return cmd


def _scp_cmd(m: dict, remote_path: str, local_dir: str) -> list[str]:
    cmd = ["scp", *_SSH_OPTS, "-r"]
    if m.get("key_path"):
        cmd += ["-i", m["key_path"]]
    cmd += [f"{_target(m)}:{remote_path}", local_dir]
    return cmd


def run(name: str, remote_command: str, timeout: int = 30) -> tuple[bool, str]:
    m = _machine_for(name)
    if m is None:
        return False, f"Não conheço a máquina '{name}'."
    if m.get("is_self"):
        return False, "Essa é esta própria máquina — use o ATLAS daqui normalmente."
    try:
        p = subprocess.run(_ssh_cmd(m, remote_command), capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, (f"'{name}' não respondeu em {timeout}s. Veja se está ligada, se o "
                       "Tailscale está ativo nela e se o OpenSSH Server está rodando.")
    except FileNotFoundError:
        return False, ("O comando 'ssh' não existe aqui. No Windows: Configurações → Apps → "
                       "Recursos opcionais → adicionar 'Cliente OpenSSH'.")
    except Exception as e:
        return False, f"Falhou ao falar com '{name}': {e}"
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    out = out or ("(sem saída)" if p.returncode == 0 else "(erro sem mensagem)")
    if p.returncode != 0 and ("Permission denied" in out or "publickey" in out):
        out += (f"\n\n⚠ Login recusado. O usuário do Windows de '{name}' deve ser diferente "
                "de '" + m["user"] + "'. Ajuste no campo 'usuário' do cartão dessa máquina "
                "(na outra máquina, veja o nome com: echo %USERNAME%), ou ligue o Tailscale SSH.")
    return p.returncode == 0, out


def test(name: str) -> tuple[bool, str]:
    ok, out = run(name, "echo ATLAS-OK", timeout=12)
    if ok and "ATLAS-OK" in out:
        return True, "Conectado — SSH respondendo."
    return False, out


def pull(name: str, remote_path: str, local_dir: str, timeout: int = 120) -> tuple[bool, str]:
    m = _machine_for(name)
    if m is None:
        return False, f"Não conheço a máquina '{name}'."
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run(_scp_cmd(m, remote_path, local_dir), capture_output=True,
                           text=True, timeout=timeout)
    except Exception as e:
        return False, f"Falhou ao copiar de '{name}': {e}"
    return (True, local_dir) if p.returncode == 0 else (False, (p.stderr or p.stdout or "erro").strip())


def open_rdp(name: str) -> tuple[bool, str]:
    m = _machine_for(name)
    if m is None:
        return False, f"Não conheço a máquina '{name}'."
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["mstsc", f"/v:{m['host']}"])
        else:
            subprocess.Popen(["xfreerdp", f"/v:{m['host']}", f"/u:{m['user']}"])
        return True, f"Abrindo a área de trabalho de '{name}'."
    except FileNotFoundError:
        return False, "Área de trabalho remota indisponível (mstsc não encontrado)."
    except Exception as e:
        return False, str(e)


def keygen_hint(name: str) -> str:
    m = _machine_for(name)
    tgt = _target(m) if m else "USUARIO@HOST"
    return ('type $env:USERPROFILE\\.ssh\\id_ed25519.pub | '
            f'ssh {tgt} "powershell -c \\"$d=$env:USERPROFILE+\'\\.ssh\'; '
            'mkdir $d -Force | Out-Null; '
            'Add-Content $d\\authorized_keys ([Console]::In.ReadToEnd())\\""')
