"""
fleet — control YOUR OTHER computers from the main one, over SSH.

THE CHOICE BEHIND THIS FILE
    "Send commands to my other PCs and see their files" has a safe shape and a
    dangerous one. The dangerous one is ATLAS opening its own network port on
    every machine and inventing its own password — that is a remote-control
    agent with homemade auth, i.e. a backdoor you installed at home. This file
    is the safe shape: ATLAS is only the PANEL. The transport is OpenSSH, which
    Windows 10/11 already ship as an optional feature. Every command and every
    file transfer rides `ssh`/`scp`, authenticated by SSH keys and encrypted end
    to end. ATLAS stores no passwords and runs no server of its own, so turning
    SSH off on a machine removes all access — there is nothing left behind.

    These are YOUR machines on YOUR network. This is ordinary remote
    administration, not access to anyone else's computer.

SETUP ON EACH MACHINE YOU WANT TO CONTROL (once)
    1. Settings → Apps → Optional Features → Add → "OpenSSH Server" → Install.
    2. In PowerShell as admin, start it and keep it on:
           Start-Service sshd
           Set-Service  sshd -StartupType Automatic
    3. Key login (so you never type a password — REQUIRED for the panel, which
       has no place to type one). On the MAIN PC:
           ssh-keygen -t ed25519            (press Enter through the prompts)
       then copy the public key to each machine (the panel prints the exact
       line, with the machine filled in):
           type $env:USERPROFILE\\.ssh\\id_ed25519.pub | ssh USER@HOST "powershell -c \\"$d=$env:USERPROFILE+'\\.ssh'; mkdir $d -Force | Out-Null; Add-Content $d\\authorized_keys ([Console]::In.ReadToEnd())\\""
    For the live desktop (RDP): on each machine, Settings → System → Remote
    Desktop → On.

WHERE THE LIST LIVES
    config/fleet.json inside the ADMIN profile only — a name, host and user per
    machine. No secrets are stored here; SSH holds the keys.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core import profile

# ssh gives up fast instead of hanging a GUI button, never falls back to an
# interactive password prompt (there is no terminal behind the panel), and does
# not stall on a first-contact host-key question.
_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
             "-o", "StrictHostKeyChecking=accept-new"]


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


def get(name: str) -> dict | None:
    name = (name or "").strip().lower()
    for m in load():
        if m.get("name", "").strip().lower() == name:
            return m
    return None


def add(name: str, host: str, user: str, key_path: str = "") -> tuple[bool, str]:
    name, host, user = name.strip(), host.strip(), user.strip()
    if not name or not host or not user:
        return False, "Preencha nome, host (IP ou nome na rede) e usuário."
    machines = [m for m in load() if m.get("name", "").strip().lower() != name.lower()]
    machines.append({"name": name, "host": host, "user": user,
                     "key_path": key_path.strip()})
    _save(machines)
    return True, f"Máquina '{name}' salva."


def remove(name: str) -> bool:
    before = load()
    after = [m for m in before if m.get("name", "").strip().lower() != name.strip().lower()]
    if len(after) == len(before):
        return False
    _save(after)
    return True


def _target(m: dict) -> str:
    return f"{m['user']}@{m['host']}"


def _ssh_cmd(m: dict, remote_command: str) -> list[str]:
    """The argv for running one command on machine `m`. Pure/That makes it
    testable without a live host."""
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
    """Run a command on a NAMED machine (never a raw host — only the fleet list)
    and return (ok, combined output)."""
    m = get(name)
    if m is None:
        return False, f"Não conheço a máquina '{name}'. Adicione-a no painel de rede."
    try:
        p = subprocess.run(_ssh_cmd(m, remote_command), capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, (f"'{name}' não respondeu em {timeout}s. Veja se ela está ligada e "
                       "se o OpenSSH Server está rodando nela.")
    except FileNotFoundError:
        return False, ("O comando 'ssh' não existe nesta máquina. No Windows: Configurações "
                       "→ Apps → Recursos opcionais → adicionar 'Cliente OpenSSH'.")
    except Exception as e:
        return False, f"Falhou ao falar com '{name}': {e}"
    out = (p.stdout or "") + (p.stderr or "")
    out = out.strip() or ("(sem saída)" if p.returncode == 0 else "(erro sem mensagem)")
    if p.returncode != 0 and ("Permission denied" in out or "publickey" in out):
        out += ("\n\n⚠ Login recusado: falta a chave SSH nesta máquina. "
                "Use o botão 'copiar chave' no painel.")
    return p.returncode == 0, out


def test(name: str) -> tuple[bool, str]:
    ok, out = run(name, "echo ATLAS-OK", timeout=12)
    if ok and "ATLAS-OK" in out:
        return True, "Conectado — SSH respondendo."
    return False, out


def pull(name: str, remote_path: str, local_dir: str, timeout: int = 120) -> tuple[bool, str]:
    """Copy a file/folder off a machine (scp) so you can see its files locally."""
    m = get(name)
    if m is None:
        return False, f"Não conheço a máquina '{name}'."
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run(_scp_cmd(m, remote_path, local_dir), capture_output=True,
                           text=True, timeout=timeout)
    except Exception as e:
        return False, f"Falhou ao copiar de '{name}': {e}"
    if p.returncode == 0:
        return True, local_dir
    return False, (p.stderr or p.stdout or "erro").strip()


def open_rdp(name: str) -> tuple[bool, str]:
    """Open the live remote desktop (Windows Remote Desktop / mstsc)."""
    m = get(name)
    if m is None:
        return False, f"Não conheço a máquina '{name}'."
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["mstsc", f"/v:{m['host']}"])
        else:                                  # dev convenience off Windows
            subprocess.Popen(["xfreerdp", f"/v:{m['host']}", f"/u:{m['user']}"])
        return True, f"Abrindo a área de trabalho de '{name}'."
    except FileNotFoundError:
        return False, "Área de trabalho remota indisponível (mstsc não encontrado)."
    except Exception as e:
        return False, str(e)


def keygen_hint(name: str) -> str:
    """The exact one-liner to authorize this PC's key on a given machine."""
    m = get(name)
    tgt = _target(m) if m else "USUARIO@HOST"
    return ('type $env:USERPROFILE\\.ssh\\id_ed25519.pub | '
            f'ssh {tgt} "powershell -c \\"$d=$env:USERPROFILE+\'\\.ssh\'; '
            'mkdir $d -Force | Out-Null; '
            'Add-Content $d\\authorized_keys ([Console]::In.ReadToEnd())\\""')
