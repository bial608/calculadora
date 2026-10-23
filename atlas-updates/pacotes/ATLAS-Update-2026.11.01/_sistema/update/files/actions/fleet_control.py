"""
controlar_computador — run a command on one of YOUR other computers by voice.

"ATLAS, no PC da sala, abre o Chrome" → this routes the command over SSH to the
machine named in the fleet list (core/fleet.py) and reads back what it said.

It can only reach machines already in the admin's fleet list — it never takes a
raw host — so a misheard name fails safe instead of touching an unknown box. See
core/fleet.py for the SSH-only, no-backdoor design and the one-time setup.
"""
from __future__ import annotations

from core import fleet


def controlar_computador(parameters: dict, player=None) -> str:
    maquina = str((parameters or {}).get("maquina", "")).strip()
    comando = str((parameters or {}).get("comando", "")).strip()
    if not maquina or not comando:
        return "Diga em qual máquina e qual comando (ex.: 'no PC sala, rode shutdown /r')."

    # Respect the kill switch: if the user hit stop, no remote command goes out.
    try:
        from core import guard
        if guard.is_killed():
            return "Kill switch ativo — não vou mandar comandos para outras máquinas agora."
    except Exception:
        pass

    if fleet.get(maquina) is None:
        known = ", ".join(m["name"] for m in fleet.load()) or "nenhuma cadastrada"
        return (f"Não conheço a máquina '{maquina}'. Conhecidas: {known}. "
                "Adicione no painel ADMIN → rede.")

    ok, out = fleet.run(maquina, comando)
    head = "✅" if ok else "⚠️"
    return f"{head} {maquina}: {out}"


TOOL = {
    "name": "controlar_computador",
    "description": (
        "Runs a command on ANOTHER of the user's own computers over SSH and "
        "returns its output. Use ONLY when the user names one of their other "
        "machines (e.g. 'no PC da sala', 'no notebook'). 'maquina' must be the "
        "machine's name as the user registered it in the fleet; 'comando' is a "
        "shell/PowerShell command for that machine. If the machine is unknown "
        "or SSH is not set up, the result says so plainly — relay that, do not "
        "claim the command ran."
    ),
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "maquina": {
                "type": "STRING",
                "description": "Name of the target computer in the user's fleet list",
            },
            "comando": {
                "type": "STRING",
                "description": "The command to run on that computer",
            },
        },
        "required": ["maquina", "comando"],
    },
    "handler": controlar_computador,
}
