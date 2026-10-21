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
def _screenshot() -> tuple[bytes, str]:
    """(jpeg bytes, fingerprint) of the primary screen — the same screen
    pyautogui clicks on."""
    from PIL import Image
    try:
        img = pyautogui.screenshot()
    except Exception:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
    img = img.convert("RGB")
    small = img.convert("L").resize((48, 27))
    fp = hashlib.md5(bytes(p // 12 for p in small.getdata())).hexdigest()
    img.thumbnail((1366, 1366))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=78)
    return buf.getvalue(), fp


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


def _to_px(x, y) -> tuple[int, int]:
    w, h = pyautogui.size()
    fx = min(max(float(x), 0.0), 1000.0) / 1000.0
    fy = min(max(float(y), 0.0), 1000.0) / 1000.0
    return int(fx * (w - 1)), int(fy * (h - 1))


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
        px, py = _to_px(a.get("x", 500), a.get("y", 500))
        if t == "double_click":
            pyautogui.doubleClick(px, py)
        elif t == "right_click":
            pyautogui.rightClick(px, py)
        else:
            pyautogui.click(px, py)
        _settle()
        return f"{t} at {px},{py} ({a.get('target', '')})"
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

Coordinates: x and y normalised 0-1000 over the screenshot (x from the left
edge, y from the top edge), at the CENTER of the element to hit.

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
             "name": "...", "url": "...", "x": 0, "y": 0, "target": "what you click",
             "text": "...", "enter": false, "keys": ["ctrl","f"], "key": "enter",
             "times": 1, "direction": "down", "amount": 5, "seconds": 1.5}},
  "why": "short reason",
  "summary": "only for done/failed/needs_user: one or two sentences to the user, in Brazilian Portuguese"}}"""


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
        return _loop(goal, cfg)
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


def _loop(goal: str, cfg: dict) -> tuple[str, str]:
    deadline = time.monotonic() + float(cfg.get("max_minutes") or 5) * 60
    max_steps = int(cfg.get("max_steps") or 30)
    model = str(cfg.get("vision_model") or "gemini-2.5-flash")

    _emit(f"tarefa: {goal}")
    activity.record("task", f"comecei: {goal}")
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
        sig = json.dumps(action, sort_keys=True) + "|" + fp
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

        result = _execute(action)
        line = (f"{step}. [{d.get('plan_step', '?')}] {action.get('type')} "
                f"{action.get('target') or action.get('name') or action.get('text') or action.get('keys') or ''}"
                f" → {result} · tela: {screen}")
        history.append(line)
        _emit(line)
        activity.record("agent_step", f"{action.get('type')}: {action.get('target') or action.get('name') or ''}".strip(": "))
    return "failed", f"Cheguei ao limite de {max_steps} passos sem concluir."


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
            say("[TASK RESULT — executar_tarefa] Tell the user in one or two short "
                "sentences, in their language, what happened. Status: "
                f"{status}. {summary}"
                + (" Ask the user the question in the summary and, when they answer, "
                   "call executar_tarefa again with the goal plus their answer."
                   if status == "needs_user" else ""))


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
