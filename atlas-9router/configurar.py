"""
Assistente de configuração em terminal — Gemini (ouvidos/voz) + 9Router (cérebro).

Roda sozinho na primeira vez pelo INICIAR_ATLAS.bat, ou a qualquer momento com:
    python configurar.py
Tudo também pode ser alterado depois dentro do app: ⚙ → 9ROUTER BRAIN (Ctrl+9).
"""
import json
import platform
import sys
from getpass import getpass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CFG = HERE / "config" / "api_keys.json"

G, Y, R, D, X = "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[0m"
if platform.system() == "Windows":
    import os
    os.system("")          # liga cores ANSI no console do Windows


def ask(label: str, default: str = "", secret: bool = False) -> str:
    shown = (default[:4] + "…" if secret and default else default)
    prompt = f"{G}?{X} {label}" + (f" {D}[{shown}]{X}" if shown else "") + ": "
    val = (getpass(prompt) if secret else input(prompt)).strip()
    return val or default


def main() -> None:
    data = {}
    if CFG.exists():
        try:
            data = json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    nr = data.get("ninerouter") or {}

    print(f"\n{G}λ atlas@mark-lvi:~$ ./configurar{X}\n")
    print(f"{D}1/2  GEMINI — ouve o microfone, vê a tela e fala a resposta{X}")
    print(f"{D}     chave grátis: https://aistudio.google.com/apikey{X}")
    data["gemini_api_key"] = ask("Gemini API key", data.get("gemini_api_key", ""), secret=True)
    if (data.get("assistant_name") or "").strip().upper() in ("", "JARVIS", "J.A.R.V.I.S"):
        data["assistant_name"] = "ATLAS"
    data.setdefault("os_system", {"Windows": "windows", "Darwin": "mac"}
                    .get(platform.system(), "linux"))

    print(f"\n{D}2/2  9ROUTER — quem pensa e responde (rode antes: npx 9router){X}")
    print(f"{D}     dashboard: http://localhost:20128  →  API Keys / Providers / Models{X}")
    nr["base_url"] = ask("Endereço do 9Router", nr.get("base_url") or "http://localhost:20128/v1")
    nr["api_key"] = ask("API key do 9Router (vazio se não exige)", nr.get("api_key", ""), secret=True)

    from core import ninerouter
    nr["base_url"] = ninerouter.normalise_url(nr["base_url"])
    if not nr["api_key"]:
        k = ninerouter.local_api_key()
        if k:
            nr["api_key"] = k
            print(f"{G}✔ API key encontrada no 9Router deste computador{X}")
    found = ninerouter.detect(nr)
    combos = [c["name"] for c in found["combos"]]
    models = combos + found["models"]
    if combos:
        print(f"{G}✔ {len(combos)} combo(s){X}")
        for i, c in enumerate(found["combos"], 1):
            chain = " → ".join(c.get("models") or [])
            print(f"   {D}{i:>2}.{X} ◈ {c['name']}" + (f"  {D}{chain}{X}" if chain else ""))
    if found["models"]:
        print(f"{G}✔ {len(found['models'])} modelo(s){X}")
        for i, m in enumerate(found["models"][:40], len(combos) + 1):
            print(f"   {D}{i:>2}.{X} {m}")
    for n in found["notes"]:
        print(f"{Y}! {n}{X}")
    if not models:
        print(f"{D}  nada detectado agora — dá pra configurar depois no app (Ctrl+9){X}")

    pick = ask("Combo ou modelo (nome ou número)", nr.get("model", ""))
    if pick.isdigit() and models and 1 <= int(pick) <= len(models):
        pick = models[int(pick) - 1]
    nr["model"] = pick
    nr["enabled"] = bool(pick)
    data["ninerouter"] = {**ninerouter.DEFAULTS, **nr}

    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps(data, indent=4), encoding="utf-8")

    if pick:
        ok, msg = ninerouter.test(data["ninerouter"])
        print((G + "✔ " if ok else R + "✖ ") + msg + X)
    print(f"\n{G}✔ salvo em config/api_keys.json{X}  — ponte 9Router: "
          f"{'LIGADA' if nr['enabled'] else 'DESLIGADA (sem modelo)'}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ncancelado.")
