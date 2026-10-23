"""
executar_tarefa — ATLAS does the WHOLE job, not one step per request.

THE PROBLEM IT SOLVES
    "Send Maria a WhatsApp saying I'm late" used to need three requests: open
    WhatsApp, search for Maria, type and send. Gemini Live calls one tool, speaks,
    and waits for the user. Nothing made it carry on.

HOW IT WORKS
    1. PLAN — 9Router (text only, same brain as the conversation; Gemini when
       the bridge is off) breaks the goal into short UI steps.
    2. LOOK → ACT → CHECK, until the goal is visibly done:
         screenshot of the screen + active window title
         -> Gemini (vision) returns ONE action as JSON: open_app, open_url,
            click(x, y), type, hotkey, press, scroll, wait
         -> the action is executed with pyautogui
         -> wait until the screen stops changing, look again
       Coordinates are normalised (0-1000) and mapped onto the real screen, so
       display scaling does not throw clicks off.
    3. STUCK — the same action on the same screen twice means it is not
       working: 9Router is asked for a new plan from what the screen shows (as
       text). Two replans, then it gives up and says why.
    4. DONE — only when the result is visible on screen (e.g. the sent message
       in the chat). The outcome is spoken and logged.

SAFETY
    * It stops for the user (needs_user) before passwords, payments,
      purchases, deleting things or accepting terms.
    * ESC (interrupt), "para a tarefa" by voice, /stop in the dev console, or
      the mouse thrown into a screen corner (pyautogui FAILSAFE) stop it.
    * Step and time limits (30 steps / 5 minutes by default).
"""
from __future__ import annotations

import hashlib
import io
import json
import platform
import re
import threading
import time
import webbrowser

from core import activity, outcome
from core.lazyimport import LazyModule


def _configure_pyautogui(module) -> None:
    module.FAILSAFE = True          # mouse into a corner = emergency stop
    module.PAUSE = 0.05


pyautogui = LazyModule("pyautogui", _configure_pyautogui)
pyperclip = LazyModule("pyperclip")

_OS = platform.system()             # Windows | Darwin | Linux
_OS_NAME = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(_OS, _OS)

_DEFAULTS = {
    "max_steps": 30,
    "max_minutes": 5,
    "minimize": True,               # hide ATLAS's window while working
    "vision_model": "gemini-2.5-flash",
    "refine_clicks": True,          # zoom in for a second, precise look before clicking
}

_stop = threading.Event()
_default_player = {"ui": None}


def set_player(ui) -> None:
    """main.py registers the UI once, so callers without one (send_message's
    background thread) still get the window minimised and the result logged."""
    _default_player["ui"] = ui

_state = {"running": False, "goal": "", "step": 0, "started": 0.0}
_run_lock = threading.Lock()


def _settings() -> dict:
    try:
        from memory.config_manager import load_api_keys
        saved = load_api_keys().get("task_agent") or {}
    except Exception:
        saved = {}
    return {**_DEFAULTS, **saved}


def stop() -> bool:
    """Ask a running task to stop at the next step. True when one was running."""
    if _state["running"]:
        _stop.set()
        return True
    return False


def busy() -> bool:
    return _state["running"]


def _emit(text: str, level: str = "info") -> None:
    print(f"[Agent] {text}")
    try:
        from core import ninerouter
        ninerouter.emit("agent", text=text, level=level)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Eyes
# ─────────────────────────────────────────────────────────────────────────────
def _grab_image():
    """Full-resolution PIL image of the primary screen (the one pyautogui
    clicks on). Kept full-res so a crop can be zoomed for precise clicking."""
    from PIL import Image
    try:
        img = pyautogui.screenshot()
    except Exception:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
    return img.convert("RGB")


def _encode(img, max_side: int = 1366, quality: int = 80) -> bytes:
    import io as _io
    im = img.copy()
    im.thumbnail((max_side, max_side))
    buf = _io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


# The most recent full-res screenshot, so a click can zoom into it for accuracy.
_last_img = {"img": None}


def _screenshot() -> tuple[bytes, str]:
    """(jpeg bytes for the model, fingerprint) of the primary screen."""
    img = _grab_image()
    _last_img["img"] = img
    small = img.convert("L").resize((48, 27))
    fp = hashlib.md5(bytes(p // 12 for p in small.getdata())).hexdigest()
    return _encode(img), fp


def _fingerprint() -> str:
    try:
        return _screenshot()[1]
    except Exception:
        return ""


def _active_title() -> str:
    try:
        import pygetwindow as gw
        return gw.getActiveWindowTitle() or ""
    except Exception:
        return ""


def _settle(max_wait: float = 3.0) -> None:
    """Return once the screen has stopped changing (two equal looks in a row)."""
    end = time.monotonic() + max_wait
    prev = _fingerprint()
    while time.monotonic() < end and not _stop.is_set():
        time.sleep(0.35)
        cur = _fingerprint()
        if cur and cur == prev:
            return
        prev = cur


# ─────────────────────────────────────────────────────────────────────────────
#  Hands
# ─────────────────────────────────────────────────────────────────────────────
_KEY_ALIASES = {"cmd": "command", "control": "ctrl", "windows": "win", "super": "win",
                "return": "enter", "escape": "esc", "del": "delete", "option": "alt"}


def _key(k: str) -> str:
    k = str(k or "").strip().lower()
    return _KEY_ALIASES.get(k, k)


def _clamp(v: float) -> float:
    return min(max(float(v), 0.0), 1000.0)


def _norm_to_px(nx: float, ny: float, w: int, h: int) -> tuple[int, int]:
    return int(_clamp(nx) / 1000.0 * (w - 1)), int(_clamp(ny) / 1000.0 * (h - 1))


def _target_norm(a: dict) -> tuple[float, float] | None:
    """Where to click, as normalised 0-1000 (nx, ny) over the screenshot.

    Gemini is trained to point in [y, x] order and to box things as
    [ymin, xmin, ymax, xmax], both 0-1000 — NOT the (x, y) the old prompt
    asked for, which is exactly why clicks landed near but not on the target.
    `box` is preferred (its centre); `point` is [y, x]; x/y are a last resort.
    """
    box = a.get("box") or a.get("box_2d")
    if isinstance(box, (list, tuple)) and len(box) == 4:
        ymin, xmin, ymax, xmax = (float(v) for v in box)
        return (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    pt = a.get("point")
    if isinstance(pt, (list, tuple)) and len(pt) == 2:
        return float(pt[1]), float(pt[0])          # [y, x] -> (nx, ny)
    if a.get("x") is not None and a.get("y") is not None:
        return float(a["x"]), float(a["y"])
    return None


def _refine_click(target: str, base_px: int, base_py: int, w: int, h: int) -> tuple[int, int]:
    """Second look, zoomed in: crop a region at full resolution around the first
    guess, enlarge it and ask Gemini for the precise point INSIDE the crop. On a
    crop the element is big, so the answer is far more accurate than on the whole
    screen. Any failure keeps the first guess."""
    img = _last_img["img"]
    if img is None or not target:
        return base_px, base_py
    try:
        from google.genai import types
        from core import gemini
        cw, ch = int(w * 0.30), int(h * 0.30)       # 30% window around the guess
        left, top = max(0, base_px - cw // 2), max(0, base_py - ch // 2)
        right, bottom = min(w, left + cw), min(h, top + ch)
        left, top = right - cw, bottom - ch
        crop = img.crop((left, top, right, bottom))
        big = crop.resize((cw * 2, ch * 2))
        data = gemini.as_json(
            [types.Part.from_bytes(data=_encode(big, 1100, 85), mime_type="image/jpeg"),
             f'This is a zoomed-in crop of the screen. Point at the exact centre of '
             f'"{target}". Reply ONLY {{"point": [y, x]}} normalised 0-1000 over THIS '
             f'crop, or {{"point": null}} if it is not visible here.'],
            tier="gemini-2.5-flash", timeout_ms=20_000)
        pt = (data or {}).get("point")
        if isinstance(pt, (list, tuple)) and len(pt) == 2:
            ny, nx = float(pt[0]), float(pt[1])
            px = left + int(_clamp(nx) / 1000.0 * cw)
            py = top + int(_clamp(ny) / 1000.0 * ch)
            return px, py
    except Exception as e:
        _emit(f"refino do clique falhou ({e}); usando a 1ª posição", "warn")
    return base_px, base_py


def _snap_windows(px: int, py: int) -> tuple[int, int]:
    """Windows only: snap onto the UI element under the point, so a click that
    is slightly off still lands on the button's centre. Best-effort."""
    if _OS != "Windows":
        return px, py
    try:
        from pywinauto.uia_defs import IUIA  # noqa: F401  (import guard)
        from pywinauto import Desktop
        el = Desktop(backend="uia").from_point(px, py)
        r = el.rectangle()
        if 4 < r.width() < 900 and 4 < r.height() < 220:   # a control, not a pane
            return r.mid_point().x, r.mid_point().y
    except Exception:
        pass
    return px, py


def _paste(text: str) -> None:
    """Typing through the clipboard: accents, emoji and any keyboard layout work."""
    old = None
    try:
        old = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("command" if _OS == "Darwin" else "ctrl", "v")
    time.sleep(0.15)
    if old is not None:
        threading.Timer(1.0, lambda: _safe_copy(old)).start()


def _safe_copy(text):
    try:
        pyperclip.copy(text)
    except Exception:
        pass


def _execute(a: dict) -> str:
    t = str(a.get("type") or "").lower()
    if t == "open_app":
        from actions.open_app import open_app
        r = open_app({"app_name": str(a.get("name") or "")})
        _settle(5.0)
        return r.split("\n")[0][:160]
    if t == "open_url":
        webbrowser.open(str(a.get("url") or ""))
        _settle(5.0)
        return "url opened"
    if t in ("click", "double_click", "right_click"):
        w, h = pyautogui.size()
        norm = _target_norm(a)
        if norm is None:
            return "no coordinates given for the click"
        px, py = _norm_to_px(norm[0], norm[1], w, h)
        target = str(a.get("target") or "")
        if _settings().get("refine_clicks", True):
            px, py = _refine_click(target, px, py, w, h)
        px, py = _snap_windows(px, py)
        pyautogui.moveTo(px, py, duration=0.15)
        if t == "double_click":
            pyautogui.doubleClick(px, py)
        elif t == "right_click":
            pyautogui.rightClick(px, py)
        else:
            pyautogui.click(px, py)
        _settle()
        return f"{t} em {px},{py} ({target})"
    if t == "type":
        _paste(str(a.get("text") or ""))
        if a.get("enter"):
            time.sleep(0.2)
            pyautogui.press("enter")
        _settle()
        return f"typed {len(str(a.get('text') or ''))} chars" + (" + enter" if a.get("enter") else "")
    if t == "hotkey":
        keys = [_key(k) for k in (a.get("keys") or [])]
        if keys:
            pyautogui.hotkey(*keys)
        _settle()
        return "hotkey " + "+".join(keys)
    if t == "press":
        k, n = _key(a.get("key")), max(1, min(int(a.get("times") or 1), 20))
        pyautogui.press(k, presses=n, interval=0.08)
        _settle()
        return f"press {k} x{n}"
    if t == "scroll":
        amt = max(1, min(int(a.get("amount") or 5), 30)) * 100
        pyautogui.scroll(-amt if str(a.get("direction", "down")).lower() == "down" else amt)
        _settle()
        return f"scroll {a.get('direction', 'down')}"
    if t == "wait":
        s = max(0.5, min(float(a.get("seconds") or 1.5), 10.0))
        _stop.wait(s)
        return f"waited {s:.1f}s"
    return f"unknown action '{t}'"


# ─────────────────────────────────────────────────────────────────────────────
#  Brain
# ─────────────────────────────────────────────────────────────────────────────
_PLAN_PROMPT = """You plan tasks for a desktop agent that controls a {os} computer with the
mouse and keyboard while looking at the screen. Break the user's goal into 2-10
short, concrete steps the agent can perform and SEE succeed. Prefer the app's own
search boxes and keyboard shortcuts for {os}. The last step must be a visible
check that the goal is done (for a message: the message appears sent in the chat).
Do not add steps that ask the user anything unless the goal is truly ambiguous.
{extra}
Reply with ONLY a JSON array of strings, in Brazilian Portuguese.

GOAL: {goal}"""

_STEP_PROMPT = """You are the hands of {name}, a desktop assistant on {os}. Look at the screenshot
and choose the ONE next action that moves toward the goal.

GOAL: {goal}
PLAN:
{plan}
ACTIVE WINDOW: {title}
RECENT ACTIONS (oldest first):
{history}

To click, give a "box" = [ymin, xmin, ymax, xmax] tightly around the element,
normalised 0-1000 over the screenshot (y from the top, x from the left). ATLAS
clicks its centre and zooms in to refine, so a tight box matters more than a
perfect centre. Box the element itself (the button, the field, the contact
row), never the whole area around it.

Rules
- Complete the WHOLE goal without asking the user to split it. Skip plan steps
  the screen shows are already done; adapt if the screen differs from the plan.
- Before typing, make sure the right field is focused (click it first).
- Messages: type exactly the text the user asked for, in their language.
- WhatsApp Desktop/Web: search box at the top of the chat list (Ctrl+F also
  focuses it), click the contact in the results, click the message box at the
  bottom, type, press Enter. Make sure the chat header shows the right person.
- If a popup, update notice or tip appears, close it and continue.
- STOP with status "needs_user" before: typing passwords or codes, paying,
  buying, deleting files/accounts/chats, accepting terms, or when two contacts
  match the name and you cannot tell which one.
- Status "done" ONLY when the result is visible on screen. "failed" when it is
  impossible (app not installed, contact does not exist) — say why.
- Never repeat an action that already failed on this same screen; try another way.

Reply with ONLY this JSON:
{{"screen": "one line: what is on screen now",
  "plan_step": <number of the plan step you are on>,
  "status": "continue" | "done" | "failed" | "needs_user",
  "action": {{"type": "open_app|open_url|click|double_click|right_click|type|hotkey|press|scroll|wait",
             "name": "...", "url": "...", "box": [ymin, xmin, ymax, xmax],
             "target": "what you click", "text": "...", "enter": false,
             "keys": ["ctrl","f"], "key": "enter", "times": 1,
             "direction": "down", "amount": 5, "seconds": 1.5}},
  "actions": "OPTIONAL: in fast mode, a list of 2-4 actions you are SURE to do in a row on THIS screen to save time. Only the FIRST may be a click; the rest must be keyboard/type/press/hotkey/wait. Leave empty when unsure — ATLAS will look again.",
  "why": "short reason",
  "summary": "only for done/failed/needs_user: one or two sentences to the user, in Brazilian Portuguese"}}"""

# In fast mode only the first action in a batch may move the mouse; everything
# after it must be blind-safe (keyboard), because the screen has changed and we
# have not looked again.
_BATCH_SAFE = {"type", "type_enter", "hotkey", "press", "wait"}


def _llm_text(prompt: str) -> str:
    try:
        from core import ninerouter
        if ninerouter.enabled():
            return ninerouter.complete(prompt, timeout=60)
    except Exception as e:
        _emit(f"9Router não planejou ({e}); usando Gemini")
    from core import gemini
    return gemini.text(prompt, tier=gemini.SMART, timeout_ms=40_000)


def _parse_list(raw: str) -> list[str]:
    if "[" in raw and "]" in raw:
        try:
            data = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
            return [str(s).strip() for s in data if str(s).strip()][:12]
        except Exception:
            pass
    lines = [re.sub(r"^\s*(\d+[.)]|[-*])\s*", "", l).strip() for l in raw.splitlines()]
    return [l for l in lines if l][:12]


def _plan(goal: str, extra: str = "") -> list[str]:
    try:
        steps = _parse_list(_llm_text(_PLAN_PROMPT.format(os=_OS_NAME, goal=goal, extra=extra)))
    except Exception as e:
        _emit(f"planejamento falhou: {e}", "error")
        steps = []
    return steps or [goal]


def _decide(goal: str, plan: list[str], history: list[str], shot: bytes, model: str) -> dict:
    from google.genai import types
    from core import gemini
    try:
        from core import ninerouter
        name = ninerouter._assistant_name()
    except Exception:
        name = "ATLAS"
    prompt = _STEP_PROMPT.format(
        name=name, os=_OS_NAME, goal=goal,
        plan="\n".join(f"{i}. {s}" for i, s in enumerate(plan, 1)),
        title=_active_title() or "(unknown)",
        history="\n".join(history[-8:]) or "(none yet)")
    data = gemini.as_json([types.Part.from_bytes(data=shot, mime_type="image/jpeg"), prompt],
                          tier=model, timeout_ms=40_000)
    return data if isinstance(data, dict) else {}


# ─────────────────────────────────────────────────────────────────────────────
#  The loop
# ─────────────────────────────────────────────────────────────────────────────
def run_sync(goal: str, player=None, _claimed: bool = False) -> tuple[str, str]:
    """Run a task to the end. -> (status, summary). status: done | failed |
    needs_user | stopped."""
    if not _claimed and not _run_lock.acquire(blocking=False):
        return "failed", f"Já estou executando outra tarefa: {_state['goal']}"
    cfg = _settings()
    player = player or _default_player["ui"]
    _stop.clear()
    _state.update(running=True, goal=goal, step=0, started=time.time())
    minimized = False
    try:
        if cfg.get("minimize") and player is not None and hasattr(player, "minimize_window"):
            player.minimize_window()
            minimized = True
            time.sleep(0.6)
        skill = None
        try:
            from core import skills
            skill = skills.match(goal)
        except Exception:
            pass
        done: list[dict] = []
        status, summary = _loop(goal, cfg, skill, done)
        _learn_or_record(goal, skill, status, done)
        return status, summary
    except Exception as e:
        if type(e).__name__ == "FailSafeException":
            return "stopped", "Parei: o mouse foi levado ao canto da tela (parada de emergência)."
        _emit(f"erro: {e}", "error")
        return "failed", f"A tarefa falhou com um erro: {e}"
    finally:
        if minimized:
            try:
                player.restore_window()
            except Exception:
                pass
        _state["running"] = False
        _run_lock.release()


def _loop(goal: str, cfg: dict, skill: dict | None = None,
          done: list | None = None) -> tuple[str, str]:
    deadline = time.monotonic() + float(cfg.get("max_minutes") or 5) * 60
    max_steps = int(cfg.get("max_steps") or 30)
    model = str(cfg.get("vision_model") or "gemini-2.5-flash")
    done = done if done is not None else []

    _emit(f"tarefa: {goal}")
    activity.record("task", f"comecei: {goal}")
    if skill:
        from core import skills
        plan = skills.steps_as_plan(skill)
        _emit(f"seguindo a habilidade '{skill['name']}' ({len(plan)} passos)")
    else:
        plan = _plan(goal)
    _emit("plano: " + " │ ".join(f"{i}. {s}" for i, s in enumerate(plan, 1)))

    history: list[str] = []
    last_sig, stuck, replans, fails = "", 0, 0, 0
    for step in range(1, max_steps + 1):
        if _stop.is_set():
            return "stopped", "Parei a tarefa como você pediu."
        if time.monotonic() > deadline:
            return "failed", f"Passou do tempo limite. Fiz {step - 1} passos: " + \
                   (history[-1] if history else "")
        _state["step"] = step
        shot, fp = _screenshot()
        d = _decide(goal, plan, history, shot, model)
        if not d:
            fails += 1
            if fails >= 3:
                return "failed", "Não consegui analisar a tela (o Gemini não respondeu)."
            time.sleep(1.0)
            continue
        fails = 0
        status = str(d.get("status") or "continue").lower()
        screen = str(d.get("screen") or "")[:160]
        if status in ("done", "failed", "needs_user"):
            summary = str(d.get("summary") or d.get("why") or status)
            _emit(f"{status}: {summary}", "ok" if status == "done" else "warn")
            return status, summary

        action = d.get("action") or {}
        # Fast mode: run a short batch the model is sure of before looking again.
        batch = [action]
        if cfg.get("fast_mode") and isinstance(d.get("actions"), list) and d["actions"]:
            cand = [a for a in d["actions"] if isinstance(a, dict) and a.get("type")]
            if cand:
                batch = [cand[0]]
                for a in cand[1:4]:
                    if str(a.get("type")).lower() in _BATCH_SAFE:
                        batch.append(a)
                    else:
                        break
        sig = json.dumps(batch, sort_keys=True) + "|" + fp
        stuck = stuck + 1 if sig == last_sig else 0
        last_sig = sig
        if stuck >= 1:
            if replans >= 2:
                return "failed", ("Fiquei preso repetindo a mesma ação. Última tela: "
                                  f"{screen}")
            replans += 1
            _emit("sem progresso — pedindo um plano novo", "warn")
            plan = _plan(goal, extra=("The previous attempt is stuck. Current screen: "
                                      f"{screen}\nActions so far:\n" + "\n".join(history[-8:])))
            _emit("novo plano: " + " │ ".join(plan))
            last_sig, stuck = "", 0
            continue

        results = []
        for act in batch:
            if _stop.is_set():
                break
            results.append(_execute(act))
            done.append(act)
            activity.record("agent_step",
                            f"{act.get('type')}: {act.get('target') or act.get('name') or ''}".strip(": "))
        tag = f"{len(batch)}x " if len(batch) > 1 else ""
        line = (f"{step}. [{d.get('plan_step', '?')}] {tag}{action.get('type')} "
                f"{action.get('target') or action.get('name') or action.get('text') or action.get('keys') or ''}"
                f" → {results[-1] if results else '—'} · tela: {screen}")
        history.append(line)
        _emit(line)
    return "failed", f"Cheguei ao limite de {max_steps} passos sem concluir."


_GENERALISE = """A desktop task just succeeded. Turn the actions ATLAS performed into a
reusable recipe. Replace the concrete values that came from THIS request (a
contact name, a message, a search term, a file name) with placeholders like
{contato}, {mensagem}, {busca} — but keep fixed things (app names, shortcuts)
as they are. Keep only the steps that mattered; drop stray clicks and waits.

REQUEST: {goal}
ACTIONS (in order):
{actions}

Reply ONLY this JSON, in Brazilian Portuguese for names/triggers:
{{"name": "short skill title",
  "triggers": ["3-5 ways the user might ask for this, lowercase"],
  "params": ["contato", "mensagem"],
  "steps": [{{"kind": "open_app|open_url|hotkey|press|type|type_enter|click|double_click|right_click|scroll|wait|user",
             "arg": "value or {{placeholder}}", "target": "for clicks: what is clicked"}}]}}"""


def _generalise(goal: str, actions: list[dict]) -> dict | None:
    compact = []
    for a in actions:
        compact.append({k: a[k] for k in ("type", "name", "url", "target", "text",
                                          "keys", "key", "direction") if a.get(k)})
    try:
        raw = _llm_text(_GENERALISE.replace("{goal}", goal)
                        .replace("{actions}", json.dumps(compact, ensure_ascii=False)))
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        # normalise step kinds coming from the model's action vocabulary
        kmap = {"type": "type", "type_enter": "type_enter"}
        for st in data.get("steps", []):
            st["kind"] = kmap.get(st.get("kind"), st.get("kind"))
        return data if data.get("steps") else None
    except Exception as e:
        _emit(f"não consegui generalizar a habilidade ({e})", "warn")
        return None


def _learn_or_record(goal: str, skill: dict | None, status: str, done: list[dict]) -> None:
    try:
        from core import skills
    except Exception:
        return
    if skill:
        skills.record_run(skill["name"], status == "done")
        return
    if status == "done" and len(done) >= 2:
        g = _generalise(goal, done)
        if g and g.get("name"):
            skills.learn(g["name"], g.get("steps", []), g.get("triggers", []),
                         g.get("params", []), origin="aprendida sozinho")


def _run_and_report(goal: str, player) -> None:
    player = player or _default_player["ui"]
    status, summary = run_sync(goal, player, _claimed=True)
    activity.record("task", f"{status}: {goal} — {summary}")
    if player is not None:
        try:
            player.write_log(f"[tarefa] {status}: {summary}")
        except Exception:
            pass
        say = getattr(player, "request_say", None)
        if callable(say):
            extra = ""
            if status == "needs_user":
                extra = (" Ask the user the question in the summary and, when they "
                         "answer, call executar_tarefa again with the goal plus their answer.")
            elif status == "failed":
                extra = (" Then offer, in one short sentence, to do it together so you "
                         "learn it: if the user agrees, call ensinar_tarefa with "
                         f"action='start' and goal='{goal[:120]}'.")
            say("[TASK RESULT — executar_tarefa] Tell the user in one or two short "
                "sentences, in their language, what happened. Status: "
                f"{status}. {summary}" + extra)


# ─────────────────────────────────────────────────────────────────────────────
#  Teaching mode — "vamos fazer juntos"
# ─────────────────────────────────────────────────────────────────────────────
# When ATLAS cannot do a task alone, you guide it one step at a time by voice.
# Each instruction becomes one action ATLAS performs and remembers; when you say
# it is done, the steps are generalised and saved as a skill for next time.
_teach = {"active": False, "goal": "", "actions": [], "notes": []}

_TEACH_STEP = """You are ATLAS, learning a desktop task by being guided one step at a time.
The user just told you the NEXT single step to do. Look at the screenshot and
return the ONE action that does exactly what they said — nothing more.

OVERALL GOAL: {goal}
USER'S INSTRUCTION FOR THIS STEP: {instruction}
ACTIVE WINDOW: {title}

Same action schema as usual. For a click, give "box" = [ymin, xmin, ymax, xmax]
(0-1000). Put in "learned" a short general description of this step for a recipe,
replacing values that came from the instruction with {{placeholders}}
(e.g. "digitar {{contato}} na busca").

Reply ONLY:
{{"action": {{"type": "open_app|open_url|hotkey|press|type|type_enter|click|double_click|right_click|scroll|wait",
   "name":"...","url":"...","box":[y,x,y,x],"target":"...","text":"...",
   "keys":["ctrl","f"],"key":"enter","times":1,"direction":"down","amount":5,"seconds":1.5}},
 "learned": "general one-line description with {{placeholders}}",
 "done_hint": false}}"""


def _single_action(goal: str, instruction: str) -> dict:
    from google.genai import types
    from core import gemini
    shot, _ = _screenshot()
    prompt = _TEACH_STEP.format(goal=goal, instruction=instruction,
                                title=_active_title() or "(unknown)")
    data = gemini.as_json([types.Part.from_bytes(data=shot, mime_type="image/jpeg"), prompt],
                          tier=str(_settings().get("vision_model") or "gemini-2.5-flash"),
                          timeout_ms=40_000)
    return data if isinstance(data, dict) else {}


def _teach_to_steps() -> list[dict]:
    """The remembered actions as skill steps (uses the model's generalisations)."""
    from core.skills import STEP_KINDS
    steps = []
    for act, note in zip(_teach["actions"], _teach["notes"]):
        t = act.get("type")
        if t not in STEP_KINDS:
            continue
        arg = (note or act.get("name") or act.get("url") or act.get("text")
               or "+".join(act.get("keys", [])) or act.get("key") or act.get("target") or "")
        steps.append({"kind": t, "arg": str(arg), "target": act.get("target", "")})
    return steps


def ensinar_tarefa(parameters: dict, player=None) -> str:
    action = str(parameters.get("action") or "step").lower()
    goal = str(parameters.get("goal") or _teach["goal"]).strip()
    instr = str(parameters.get("instruction") or "").strip()

    if action == "start":
        _teach.update(active=True, goal=goal, actions=[], notes=[])
        _emit(f"modo aprender: {goal}", "ok")
        return (f"Modo aprender ligado para: {goal}. Me diga o primeiro passo (ex.: "
                f"'abre o WhatsApp'), um de cada vez. Diga 'pronto' quando terminar, "
                f"ou 'cancela' para descartar.")
    if not _teach["active"]:
        return "No teaching session is active. Call with action='start' and a goal first."
    if action == "cancel":
        _teach.update(active=False, actions=[], notes=[])
        return "Modo aprender cancelado. Não guardei nada."
    if action == "finish":
        if len(_teach["actions"]) < 1:
            _teach["active"] = False
            return "Não fizemos nenhum passo, então não há o que guardar."
        steps = _teach_to_steps()
        _teach["active"] = False
        try:
            from core import skills
            g = _generalise(goal, _teach["actions"]) or {}
            name = g.get("name") or (goal[:48].capitalize() or "Tarefa aprendida")
            triggers = g.get("triggers") or [goal]
            params = g.get("params") or []
            # prefer the model's clean recipe, fall back to our captured steps
            final_steps = g.get("steps") or steps
            skills.learn(name, final_steps, triggers, params, origin="ensinada por você")
            return (f"Guardei '{name}' com {len(final_steps)} passos. Da próxima vez que "
                    f"você pedir isso, eu já faço sozinho.")
        except Exception as e:
            return f"Aprendi os passos, mas não consegui salvar a habilidade: {e}"

    # a guided step
    if not instr:
        return "Me diga o que fazer neste passo."
    try:
        d = _single_action(goal, instr)
        act = d.get("action") or {}
        if not act.get("type"):
            return f"Não entendi '{instr}' na tela atual. Pode dizer de outro jeito?"
        result = _execute(act)
        _teach["actions"].append(act)
        _teach["notes"].append(str(d.get("learned") or instr))
        activity.record("agent_step", f"(aprendendo) {act.get('type')}: {instr}")
        _emit(f"aprendi o passo: {instr} → {result}")
        tail = " Parece que terminamos — diga 'pronto' se acabou." if d.get("done_hint") else ""
        return f"Feito: {result}. Próximo passo?{tail}"
    except Exception as e:
        return f"Não consegui fazer esse passo: {e}. Pode tentar dizer de outra forma?"


def executar_tarefa(parameters: dict, player=None) -> str:
    action = str(parameters.get("action") or "start").lower()
    if action == "stop":
        return "Stopping the task." if stop() else "No task is running."
    if action == "status":
        if not busy():
            return "No task is running."
        return f"Running '{_state['goal']}', step {_state['step']}."
    goal = str(parameters.get("goal") or "").strip()
    if not goal:
        return outcome.failed("executar_tarefa", "no goal was given")
    # Claim the slot HERE, before the thread exists, so two quick requests can
    # never start two agents fighting over the same mouse.
    if not _run_lock.acquire(blocking=False):
        return f"Already running '{_state['goal']}'. Say 'stop the task' to cancel it."
    _state.update(running=True, goal=goal, step=0)
    threading.Thread(target=_run_and_report, args=(goal, player),
                     daemon=True, name="task-agent").start()
    return outcome.started("executar_tarefa", goal=goal[:120])


TOOL = {
    "name": "executar_tarefa",
    "description": (
        "Does a COMPLETE multi-step task on the computer by itself — looks at the "
        "screen, clicks, types and checks, until the goal is visibly done. Use it "
        "whenever a request needs more than one step inside an application: "
        "'send a WhatsApp message to Maria saying ...', 'open Spotify and play my "
        "liked songs', 'search X on YouTube and open the first video', 'fill this "
        "form', 'reply to the last email'. Put the FULL goal in 'goal' in one call, "
        "with every detail the user gave (who, what text, which app) — never split "
        "it into several requests and never ask the user to do the steps. It runs "
        "in the background: on status=started say only that you are doing it; the "
        "result is reported to you when it ends. action='stop' cancels the running "
        "task (user says stop/para/cancela); action='status' tells progress."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {"type": "STRING",
                     "description": "The whole task, with all details, in the user's language."},
            "action": {"type": "STRING", "description": "start (default) | stop | status"},
        },
        "required": [],
    },
    "handler": executar_tarefa,
    "tier": "core",
    "brief": "Do a whole multi-step task on screen (apps, messages, forms) until it is done.",
}
