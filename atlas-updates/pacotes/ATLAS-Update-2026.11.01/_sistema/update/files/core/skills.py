"""
Habilidades — the procedures ATLAS has learned, one Obsidian note each.

    <vault>/ATLAS/Habilidades/Enviar mensagem no WhatsApp.md
    (no vault: memory/habilidades/)

A skill is a short, ordered recipe of steps, with concrete values turned into
{parametros}. Each note is readable for a person AND carries a fenced ```json
block that the code reads — the JSON is the source of truth, so you can correct
ATLAS by editing that block in Obsidian.

    ---
    source: atlas
    tags: [atlas, habilidade]
    ---
    # Enviar mensagem no WhatsApp

    Parâmetros: contato, mensagem

    1. abrir app — WhatsApp
    2. atalho — ctrl+f
    3. digitar — {contato}
    4. tecla — enter
    5. clicar — caixa de mensagem na parte de baixo
    6. digitar e enviar — {mensagem}

    Aprendida sozinho · usada 4x · funcionou 4x

    ```json atlas-habilidade
    {"triggers": ["mandar mensagem no whatsapp", "whatsapp"],
     "params": ["contato", "mensagem"],
     "steps": [...]}
    ```

LIFECYCLE
    learn()    save a recipe after a task worked (or after you taught it)
    match()    find the skill for a request and fill its {parametros}
    record_run / relearn   keep stats, rewrite when a recipe stops working
"""
from __future__ import annotations

import json
import re
import sys
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()

# Step kinds a skill can contain. "user" = ATLAS stops and asks you to do it.
STEP_KINDS = ("open_app", "open_url", "hotkey", "press", "type", "type_enter",
              "click", "double_click", "right_click", "scroll", "wait", "user")

_LABEL = {"open_app": "abrir app", "open_url": "abrir site", "hotkey": "atalho",
          "press": "tecla", "type": "digitar", "type_enter": "digitar e enviar",
          "click": "clicar", "double_click": "clicar duas vezes",
          "right_click": "clicar com direito", "scroll": "rolar",
          "wait": "esperar", "user": "você faz"}

_JSON_FENCE = "```json atlas-habilidade"


def _base_dir() -> Path:
    # Per-account when logged in (see memory/config_manager.get_base_dir), else
    # the install root — so each account keeps its own learned skills fallback.
    try:
        from core import profile
        return profile.base_dir()
    except Exception:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent.parent


def folder() -> Path:
    """ATLAS/Habilidades in the vault, or memory/habilidades as a fallback."""
    try:
        from plugins import obsidian_brain as ob
        if ob._ensure_vault():
            d = ob.S.vault / ob.S.folder / "Habilidades"
            d.mkdir(parents=True, exist_ok=True)
            return d
    except Exception:
        pass
    d = _base_dir() / "memory" / "habilidades"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _record_activity(text: str) -> None:
    try:
        from core import activity
        activity.record("skill", text)
    except Exception:
        pass


def _emit(text: str) -> None:
    print(f"[Skills] {text}")
    try:
        from core import ninerouter
        ninerouter.emit("agent", text=f"📘 {text}", level="info")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Matching
# ─────────────────────────────────────────────────────────────────────────────
def _strip(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


_STOP = set("""a o os as um uma de do da dos das em no na nos nas por para pra pro com que
e ou se eu me meu minha seu sua isso esse essa este esta ele ela la ai ja agora hoje
atlas the a an to of in on for and or my me it please""".split())


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", _strip(t)) if w not in _STOP}


def _safe_name(title: str) -> str:
    t = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title or "").strip()
    t = re.sub(r"\s+", " ", t)
    return (t[:70] or "Habilidade").rstrip(". ")


# ─────────────────────────────────────────────────────────────────────────────
#  Read / write
# ─────────────────────────────────────────────────────────────────────────────
def _load_all() -> list[dict]:
    out = []
    for p in folder().glob("*.md"):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        i = txt.find(_JSON_FENCE)
        if i < 0:
            continue
        body = txt[i + len(_JSON_FENCE):]
        end = body.find("```")
        if end < 0:
            continue
        try:
            data = json.loads(body[:end].strip())
        except Exception:
            continue
        data["_file"] = str(p)
        data.setdefault("name", p.stem)
        out.append(data)
    return out


def _render(skill: dict) -> str:
    name = skill["name"]
    params = skill.get("params") or []
    stats = (f"{skill.get('origin', 'aprendida')} · usada {skill.get('uses', 0)}x · "
             f"funcionou {skill.get('ok', 0)}x")
    lines = [f"---\nsource: atlas\ntype: habilidade\ntags: [atlas, habilidade]\n"
             f"updated: {datetime.now():%Y-%m-%d}\n---",
             f"# {name}", ""]
    if params:
        lines.append("Parâmetros: " + ", ".join(params))
        lines.append("")
    for i, st in enumerate(skill.get("steps", []), 1):
        kind = st.get("kind", "")
        arg = st.get("arg") or st.get("target") or ""
        lines.append(f"{i}. {_LABEL.get(kind, kind)} — {arg}".rstrip(" —"))
    lines += ["", stats, "",
              "> Pode editar o bloco JSON abaixo para me corrigir.", "",
              _JSON_FENCE,
              json.dumps({k: skill[k] for k in ("triggers", "params", "steps", "origin",
                                                "uses", "ok") if k in skill},
                         ensure_ascii=False, indent=2),
              "```", ""]
    return "\n".join(lines)


def _save(skill: dict) -> Path:
    p = Path(skill.get("_file") or (folder() / f"{_safe_name(skill['name'])}.md"))
    with _lock:
        p.write_text(_render(skill), encoding="utf-8")
    skill["_file"] = str(p)
    return p


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────
def match(request: str, min_score: float = 0.5) -> dict | None:
    """The best skill for this request, with its params filled from the request
    where possible (left for the agent/LLM to complete otherwise). None if no
    skill is close enough."""
    req = _words(request)
    if not req:
        return None
    best, best_score = None, 0.0
    for sk in _load_all():
        phrases = list(sk.get("triggers", [])) + [sk.get("name", "")]
        score = 0.0
        for phrase in phrases:
            tw = _words(phrase)
            if tw:
                # how much of this trigger phrase the request covers (a single
                # distinctive word like "whatsapp" fully matches on its own)
                score = max(score, len(tw & req) / len(tw))
        if score > best_score:
            best, best_score = sk, score
    if best and best_score >= min_score:
        _emit(f"já sei fazer isto: {best['name']}")
        return best
    return None


def learn(name: str, steps: list[dict], triggers: list[str], params: list[str],
          origin: str = "aprendida sozinho") -> Path | None:
    """Save a new skill (or refresh one with the same name)."""
    steps = [s for s in (steps or []) if isinstance(s, dict) and s.get("kind") in STEP_KINDS]
    if not name or not steps:
        return None
    existing = {s["name"]: s for s in _load_all()}
    prior = existing.get(name, {})
    skill = {"name": name, "triggers": sorted(set(triggers or []) | set(prior.get("triggers", []))),
             "params": params or prior.get("params", []), "steps": steps,
             "origin": origin, "uses": prior.get("uses", 0), "ok": prior.get("ok", 0),
             "_file": prior.get("_file")}
    p = _save(skill)
    _emit(f"guardei a habilidade '{name}' ({len(steps)} passos) em {p.name}")
    _record_activity(f"Aprendi a fazer sozinho: {name} ({origin})")
    return p


def relearn(name: str, steps: list[dict], note: str = "") -> Path | None:
    cur = {s["name"]: s for s in _load_all()}.get(name)
    if not cur:
        return None
    cur["steps"] = [s for s in steps if isinstance(s, dict) and s.get("kind") in STEP_KINDS] or cur["steps"]
    cur["origin"] = (cur.get("origin", "aprendida") + f" · ajustada ({note})")[:120]
    _emit(f"atualizei a habilidade '{name}': {note}")
    _record_activity(f"Ajustei a habilidade '{name}': {note}")
    return _save(cur)


def record_run(name: str, ok: bool) -> None:
    cur = {s["name"]: s for s in _load_all()}.get(name)
    if not cur:
        return
    cur["uses"] = cur.get("uses", 0) + 1
    if ok:
        cur["ok"] = cur.get("ok", 0) + 1
    _save(cur)


def steps_as_plan(skill: dict, values: dict | None = None) -> list[str]:
    """Human-readable plan lines for the agent, with {params} filled in."""
    values = values or {}
    out = []
    for st in skill.get("steps", []):
        arg = str(st.get("arg") or st.get("target") or "")
        for k, v in values.items():
            arg = arg.replace("{%s}" % k, str(v))
        out.append(f"{_LABEL.get(st.get('kind'), st.get('kind'))}: {arg}".rstrip(": "))
    return out
