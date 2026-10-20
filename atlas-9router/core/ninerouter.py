"""
9Router bridge — Gemini listens, 9Router thinks.

HOW THE PIECES FIT
    Gemini Live stays exactly where it was: it holds the microphone, the voice,
    the avatar, the tools. What changes is WHO WRITES THE ANSWER. With the
    bridge on, every user turn is relayed through the `ask_9router` tool
    (actions/ninerouter_relay.py): Gemini hands over a raw-refined version of
    what it heard plus anything it can see — the screen, the camera, a dropped
    image, frames from a video — and 9Router answers. Gemini then only speaks
    that answer.

    9Router (https://github.com/decolua/9router) is a local gateway that serves
    the OpenAI protocol at http://localhost:20128/v1 and routes to whatever
    providers you configured in its dashboard. So this file is a plain
    /v1/chat/completions client, with `httpx` (already installed by google-genai).

WHERE THE SETTINGS LIVE
    config/api_keys.json -> "ninerouter": {...}, the same file every other
    setting uses. Environment variables (or a .env file next to main.py) win
    over the file, so a key never has to be written to disk if you prefer:
        NINEROUTER_BASE_URL, NINEROUTER_API_KEY, NINEROUTER_MODEL,
        NINEROUTER_ENABLED (1/0)

THE DEV CONSOLE
    Every request, answer and error is published to listeners (the UI's dev
    console subscribes), so you can watch the traffic like a network tab.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Optional


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR    = _base_dir()
CONFIG_FILE = BASE_DIR / "config" / "api_keys.json"
ENV_FILE    = BASE_DIR / ".env"

DEFAULTS: dict = {
    "enabled":       False,
    # 127.0.0.1 rather than localhost: on Windows `localhost` resolves to ::1
    # first and a server bound to IPv4 only refuses it (same reason as
    # providers/llm_openai.py).
    "base_url":      "http://127.0.0.1:20128/v1",
    "api_key":       "",
    "model":         "",
    "temperature":   0.4,
    "timeout":       90,
    "max_tokens":    1024,
    "history_turns": 6,       # previous exchanges sent back for context
    "system_prompt": "",      # extra instructions appended to the built-in one
    # TEXT-ONLY: nothing but text ever reaches 9Router. Images, screen and
    # camera captures, video frames and audio are first decoded by Gemini into
    # explicit text — every visible word verbatim, every piece of code/log/
    # error exactly, in fenced code blocks — so models without vision work.
    # Off = images go as image_url parts (needs a vision model); audio is
    # decoded either way, since /chat/completions has no audio input.
    "text_only":     True,
}

_SYSTEM_PROMPT = (
    "You are the reasoning core of a desktop voice assistant called {name}. "
    "Another model transcribes the user's speech and sends you a refined "
    "version of the request, the raw transcript, and sometimes media from the "
    "screen, the webcam or a file. Media normally arrives ALREADY DECODED into "
    "explicit text by a perception model: treat that text and its code blocks "
    "as an exact transcription of what is there (screen = the user's COMPUTER, "
    "webcam = the USER). "
    "Your answer will be SPOKEN ALOUD by a text-to-speech voice, so: answer in "
    "the same language the user spoke; be precise and direct; no markdown, no "
    "tables, no emojis, no code fences unless the user explicitly asked for "
    "code; prefer short paragraphs. If the transcript looks garbled, answer "
    "the most likely intent and say briefly what you assumed. Never invent "
    "facts: when you do not know, say so.\n"
    "IDENTITY: your name is {name}. You ARE {name}. If asked who or what you "
    "are, who made you or which model you are, answer as {name}, the user's "
    "personal assistant. Never call yourself Claude, GPT, ChatGPT, Gemini, "
    "Llama, Qwen, DeepSeek, Kimi or any other model or company name, and never "
    "mention 9Router, routers, combos or providers unless the user explicitly "
    "asks about the technical setup."
)


# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────
def _read_env_file() -> dict:
    out = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _env(name: str, file_env: dict) -> Optional[str]:
    v = os.environ.get(name)
    if v is None:
        v = file_env.get(name)
    return v if v not in (None, "") else None


_cache: dict = {"mtime": None, "cfg": None}


def load_config() -> dict:
    """Saved settings merged over DEFAULTS, then env vars over both.

    Cached against the file's mtime so it is cheap to call on every request and
    a change saved from the panel takes effect without a restart."""
    try:
        mtime = CONFIG_FILE.stat().st_mtime
    except OSError:
        mtime = None
    if _cache["cfg"] is None or _cache["mtime"] != mtime:
        saved = {}
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("ninerouter") or {}
        except Exception:
            saved = {}
        _cache["cfg"] = {**DEFAULTS, **saved}
        _cache["mtime"] = mtime

    cfg = dict(_cache["cfg"])
    fe = _read_env_file()
    for key, var in (("base_url", "NINEROUTER_BASE_URL"),
                     ("api_key",  "NINEROUTER_API_KEY"),
                     ("model",    "NINEROUTER_MODEL")):
        v = _env(var, fe)
        if v:
            cfg[key] = v
    en = _env("NINEROUTER_ENABLED", fe)
    if en is not None:
        cfg["enabled"] = en.strip().lower() in ("1", "true", "yes", "on", "sim")
    return cfg


def save_config(values: dict) -> None:
    """Read-modify-write only the "ninerouter" block of api_keys.json."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    block = {**DEFAULTS, **(data.get("ninerouter") or {})}
    for k, v in values.items():
        if k in DEFAULTS:
            block[k] = v
    data["ninerouter"] = block
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
    _cache["cfg"] = None


def enabled() -> bool:
    return bool(load_config().get("enabled"))


def normalise_url(url: str) -> str:
    """localhost -> 127.0.0.1, add a missing scheme, add /v1 when there is no path."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return DEFAULTS["base_url"]
    if "://" not in url:
        url = "http://" + url
    scheme, _, rest = url.partition("://")
    host, slash, path = rest.partition("/")
    if host.split(":")[0].lower() == "localhost":
        port = host.partition(":")[2]
        host = "127.0.0.1" + (f":{port}" if port else "")
    url = f"{scheme}://{host}{slash}{path}".rstrip("/")
    if not path:
        url += "/v1"
    return url


def _root_url(base_url: str) -> str:
    """http://127.0.0.1:20128/v1 -> http://127.0.0.1:20128"""
    u = normalise_url(base_url)
    return u[:-3] if u.endswith("/v1") else u


def _headers(cfg: dict) -> dict:
    h = {"Content-Type": "application/json"}
    key = str(cfg.get("api_key") or "").strip()
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


# ─────────────────────────────────────────────────────────────────────────────
#  Events for the dev console
# ─────────────────────────────────────────────────────────────────────────────
_listeners: list[Callable[[dict], None]] = []
_lock = threading.Lock()

stats = {
    "requests": 0,
    "errors": 0,
    "last_latency_ms": None,
    "last_model": "",
    "tokens_in": 0,
    "tokens_out": 0,
    "online": None,     # None = unknown, True/False after a ping
}


# Plugins can feed every request and learn from every answer:
#   context provider  (request) -> str | ""   text added as [CONTEXT ...]
#   answer hook       (request, answer) -> None, called after a good answer
_context_providers: list = []
_answer_hooks: list = []


def add_context_provider(fn) -> None:
    if fn not in _context_providers:
        _context_providers.append(fn)


def add_answer_hook(fn) -> None:
    if fn not in _answer_hooks:
        _answer_hooks.append(fn)


def gather_context(request: str) -> str:
    parts = []
    for fn in list(_context_providers):
        try:
            t = fn(request)
            if t:
                parts.append(str(t).strip())
        except Exception as e:
            _emit("error", text=f"context provider failed: {e}")
    return "\n\n".join(parts)


def add_listener(fn: Callable[[dict], None]) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def emit(kind: str, **data) -> None:
    """Public: plugins write to the dev console through this."""
    _emit(kind, **data)


def _emit(kind: str, **data) -> None:
    evt = {"kind": kind, "ts": time.strftime("%H:%M:%S"), **data}
    for fn in list(_listeners):
        try:
            fn(evt)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  What Gemini heard
# ─────────────────────────────────────────────────────────────────────────────
_heard = {"text": "", "at": 0.0}


def note_heard(text: str) -> None:
    """Called by main.py with the raw input transcription as it streams in."""
    _heard["text"] = (text or "").strip()
    _heard["at"] = time.monotonic()


def last_heard(max_age: float = 90.0, consume: bool = False) -> str:
    """The latest raw transcript, if recent. consume=True hands it out once, so
    a later turn (typed, or a follow-up tool call) never reuses stale words."""
    text = "" if time.monotonic() - _heard["at"] > max_age else _heard["text"]
    if consume:
        _heard["text"] = ""
    return text


_REPEAT = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE | re.UNICODE)


def refine(text: str) -> str:
    """The "raw" refinement: whitespace collapsed, stutters ("o o o que") folded,
    stray transcription noise removed. Deliberately NOT a rewrite — meaning is
    left untouched, and no language-specific word list is used."""
    t = (text or "").replace("​", " ")
    t = re.sub(r"<[^>]{1,20}>", " ", t)           # <noise>, <unk> tags
    t = re.sub(r"\s+", " ", t).strip()
    t = _REPEAT.sub(r"\1", t)
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)
    return t


# ─────────────────────────────────────────────────────────────────────────────
#  The request
# ─────────────────────────────────────────────────────────────────────────────
_history: deque = deque(maxlen=40)    # (user_text, answer) — text only


def clear_history() -> None:
    _history.clear()
    _emit("info", text="history cleared")


def _assistant_name() -> str:
    try:
        name = (json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                .get("assistant_name") or "ATLAS").strip()
        if name.upper().rstrip(".") in ("JARVIS", "J.A.R.V.I.S"):
            return "ATLAS"
        return name
    except Exception:
        return "ATLAS"


def _build_messages(cfg: dict, request: str, raw: str,
                    images: list, extra_text: str) -> list:
    sys_txt = _SYSTEM_PROMPT.format(name=_assistant_name())
    sys_txt += f"\nCurrent local time: {time.strftime('%A %Y-%m-%d %H:%M')}."
    if str(cfg.get("system_prompt") or "").strip():
        sys_txt += "\n\n" + str(cfg["system_prompt"]).strip()
    msgs: list = [{"role": "system", "content": sys_txt}]

    n = int(cfg.get("history_turns") or 0)
    if n > 0:
        for u, a in list(_history)[-n:]:
            msgs.append({"role": "user", "content": u})
            msgs.append({"role": "assistant", "content": a})

    body = f"[REQUEST]\n{request.strip()}"
    if raw and refine(raw).lower() != request.strip().lower():
        body += f"\n\n[RAW TRANSCRIPT — what the microphone heard]\n{refine(raw)}"
    if extra_text:
        body += f"\n\n[ATTACHED CONTENT]\n{extra_text}"

    if images:
        content: list = [{"type": "text", "text": body}]
        for img_bytes, mime, label in images:
            b64 = base64.b64encode(img_bytes).decode("ascii")
            if label:
                content.append({"type": "text", "text": f"[{label}]"})
            content.append({"type": "image_url",
                             "image_url": {"url": f"data:{mime};base64,{b64}"}})
        msgs.append({"role": "user", "content": content})
    else:
        msgs.append({"role": "user", "content": body})
    return msgs


def _strip_think(text: str) -> str:
    """Reasoning models' <think> blocks must never be spoken."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    text = re.sub(r"^.*?</think>", "", text, flags=re.S | re.I)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Media -> explicit text (Gemini as the decoder)
# ─────────────────────────────────────────────────────────────────────────────
_DECODE_PROMPT = """You are a PERCEPTION DECODER. A TEXT-ONLY model will reason about the
media below. It cannot see or hear anything, so your text is ALL it will ever
know about this media. Convert every item into explicit, exhaustive text.

RULES
1. Transcribe ALL visible text verbatim: titles, menus, tabs, buttons, labels,
   file names, URLs, numbers, notifications. Keep the original language.
2. Any CODE, terminal output, logs, stack traces, errors, JSON, config or SQL:
   reproduce it EXACTLY inside fenced code blocks with a language tag
   (```python, ```bash, ```text ...). Keep indentation and line order. Do NOT
   fix, shorten or summarise code. Note the file name / line numbers if shown.
3. Error dialogs and warnings: quote the exact message, say which app shows it.
4. Layout: which apps/windows are open, which is focused, what is selected or
   highlighted, where the cursor is, what part of the screen each thing is in.
5. Tables, charts, spreadsheets: convert to markdown tables / explicit values.
6. Photos, people, webcam: objective description (objects, people, actions,
   expressions, text on objects). No guessing identities.
7. Video frames: go in order, give each frame's timestamp and what changed.
8. Audio: full verbatim transcription with timestamps, then non-speech sounds.
9. Do NOT answer the user's request and do NOT give opinions — facts only.
   Mark any uncertain reading with [?].

Output one section per item, headed exactly: ### ITEM <n> — <label>
Write descriptions in the same language as the user's request.

User's request (context only, do not answer it): {request}"""


def decode_media(items: list, request: str = "") -> str:
    """[(bytes, mime, label)] -> one block of explicit text. Raises on failure."""
    from google.genai import types
    from core import gemini

    t0 = time.monotonic()
    contents: list = []
    for n, (data, mime, label) in enumerate(items, 1):
        contents.append(f"ITEM {n} — {label or mime}")
        contents.append(types.Part.from_bytes(data=data, mime_type=mime))
    contents.append(_DECODE_PROMPT.format(request=request.strip() or "(none)"))

    _emit("decode", text=f"decoding {len(items)} item(s) to text via Gemini…")
    resp = gemini.call(contents, tier=gemini.SMART, timeout_ms=90_000)
    out = (getattr(resp, "text", None) or "").strip() if resp is not None else ""
    ms = int((time.monotonic() - t0) * 1000)
    if not out:
        _emit("error", ms=ms, text="Gemini could not decode the media to text")
        raise RuntimeError("Gemini could not decode the media to text")
    _emit("decode", ms=ms, text=f"decoded → {len(out)} chars of text/code", body=out)
    return out


def ask(request: str, raw_heard: str = "", images: Optional[list] = None,
        extra_text: str = "") -> str:
    """Send one turn to 9Router and return the answer text. Raises on failure.

    images: list of (bytes, mime, label).
    """
    import httpx

    cfg = load_config()
    base = normalise_url(cfg.get("base_url", ""))
    model = str(cfg.get("model") or "").strip()
    if not model:
        raise RuntimeError("no 9Router model configured (⚙ → 9ROUTER → model)")

    # Text-only gate: anything that is not plain text is decoded first. Audio
    # always is (chat/completions has no audio input); images only in
    # text-only mode. If decoding fails, the request still goes — as text,
    # saying what could not be read — rather than smuggling bytes through.
    images = images or []
    text_only = bool(cfg.get("text_only", True))
    to_decode = [m for m in images if text_only or not str(m[1]).startswith("image/")]
    images = [m for m in images if m not in to_decode]
    if to_decode:
        try:
            decoded = decode_media(to_decode, request)
        except Exception as e:
            decoded = (f"(the user attached {len(to_decode)} media item(s) — "
                       f"{', '.join(str(m[2]) for m in to_decode)} — but they "
                       f"could not be converted to text: {e})")
        extra_text = (extra_text + "\n\n" if extra_text else "") + \
            "[MEDIA DECODED TO TEXT — exact transcription of what is on screen/in the file]\n" + decoded

    ctx = gather_context(request)
    if ctx:
        extra_text = (extra_text + "\n\n" if extra_text else "") + ctx

    msgs = _build_messages(cfg, request, raw_heard, images, extra_text)
    payload = {
        "model": model,
        "messages": msgs,
        "temperature": float(cfg.get("temperature") or 0.4),
        "stream": False,
    }
    mt = int(cfg.get("max_tokens") or 0)
    if mt > 0:
        payload["max_tokens"] = mt

    with _lock:
        stats["requests"] += 1
        rid = stats["requests"]
    _emit("request", id=rid, model=model, url=f"{base}/chat/completions",
          text=request, raw=raw_heard, images=len(images),
          attached=len(extra_text))

    t0 = time.monotonic()
    try:
        r = httpx.post(f"{base}/chat/completions", json=payload,
                       headers=_headers(cfg),
                       timeout=float(cfg.get("timeout") or 90))
        if r.status_code >= 400:
            detail = r.text[:400]
            if r.status_code in (401, 403):
                raise RuntimeError(f"9Router refused the API key (HTTP {r.status_code})")
            if r.status_code == 404:
                raise RuntimeError(f"HTTP 404 — wrong address or unknown model "
                                   f"'{model}': {detail}")
            raise RuntimeError(f"HTTP {r.status_code}: {detail}")
        data = r.json()
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):     # some gateways return parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        answer = _strip_think(content or "")
        if not answer:
            raise RuntimeError("9Router returned an empty answer")
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        with _lock:
            stats["errors"] += 1
            stats["last_latency_ms"] = ms
            if "ConnectError" in type(e).__name__ or "Connect" in str(type(e)):
                stats["online"] = False
        _emit("error", id=rid, ms=ms, text=f"{type(e).__name__}: {e}")
        if type(e).__name__ in ("ConnectError", "ConnectTimeout"):
            raise RuntimeError(f"nothing answered at {base} — is 9Router running?") from e
        raise

    ms = int((time.monotonic() - t0) * 1000)
    usage = data.get("usage") or {}
    with _lock:
        stats["last_latency_ms"] = ms
        stats["last_model"] = data.get("model") or model
        stats["tokens_in"] += int(usage.get("prompt_tokens") or 0)
        stats["tokens_out"] += int(usage.get("completion_tokens") or 0)
        stats["online"] = True
    _history.append((request.strip(), answer))
    _emit("response", id=rid, ms=ms, model=stats["last_model"], text=answer,
          usage=usage)
    for fn in list(_answer_hooks):
        try:
            fn(request, answer)
        except Exception as e:
            _emit("error", text=f"answer hook failed: {e}")
    return answer


def complete(prompt: str, system: str = "", timeout: float = 120) -> str:
    """One plain text completion for housekeeping (summaries, titles, profile).
    No history, no context providers, no answer hooks — so a plugin calling it
    can never trigger itself. Raises on failure."""
    import httpx
    cfg = load_config()
    model = str(cfg.get("model") or "").strip()
    if not model:
        raise RuntimeError("no 9Router model configured")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    t0 = time.monotonic()
    r = httpx.post(f"{normalise_url(cfg.get('base_url', ''))}/chat/completions",
                   json={"model": model, "messages": msgs, "stream": False,
                         "temperature": 0.3},
                   headers=_headers(cfg), timeout=timeout)
    r.raise_for_status()
    msg = (r.json().get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    out = _strip_think(content or "")
    _emit("info", text=f"complete() {int((time.monotonic() - t0) * 1000)}ms → {len(out)} chars")
    if not out:
        raise RuntimeError("empty completion")
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Diagnostics for the settings panel
# ─────────────────────────────────────────────────────────────────────────────
def list_models(cfg: Optional[dict] = None) -> list[str]:
    import httpx
    cfg = cfg or load_config()
    base = normalise_url(cfg.get("base_url", ""))
    r = httpx.get(f"{base}/models", headers=_headers(cfg), timeout=10)
    r.raise_for_status()
    items = r.json().get("data") or []
    return sorted({str(m.get("id")) for m in items if m.get("id")})


# ─────────────────────────────────────────────────────────────────────────────
#  Combos — 9Router's named fallback chains
# ─────────────────────────────────────────────────────────────────────────────
# A combo is called exactly like a model (its name goes in "model"), but it is
# a chain: 9Router tries each seat in order until one answers. Three sources,
# merged, so they show up whichever way this machine is set up:
#   1. GET /v1/models with the API key — combos come first, owned_by "combo"
#      (that is what 9Router's own models route emits)
#   2. GET /api/combos — the dashboard API: {"combos": [{name, models, kind}]}
#   3. the local database: ${DATA_DIR}/db.json, default ~/.9router/db.json
#      -> "combos": [{id, name, models[]}]
# Combos of kind webSearch / webFetch are not chat models and are skipped.
_NON_CHAT_KINDS = {"websearch", "webfetch", "image", "embedding", "tts", "stt"}
known_combos: dict = {}      # name -> {"models": [...], "source": "..."}


def _local_db_paths() -> list[Path]:
    out = []
    data_dir = os.environ.get("DATA_DIR") or _read_env_file().get("DATA_DIR")
    if data_dir:
        out.append(Path(data_dir).expanduser() / "db.json")
    out.append(Path.home() / ".9router" / "db.json")
    for env in ("APPDATA", "LOCALAPPDATA"):
        if os.environ.get(env):
            out.append(Path(os.environ[env]) / "9router" / "db.json")
    return out


def _read_local_db() -> dict:
    for p in _local_db_paths():
        try:
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def local_api_key() -> str:
    """The first active API key in the local 9Router database, or ''.
    Lets the panel fill the key in when 9Router runs on this machine."""
    for k in _read_local_db().get("apiKeys") or []:
        if isinstance(k, dict) and k.get("key") and k.get("isActive", True):
            return str(k["key"])
    return ""


def _chat_combo(c: dict) -> bool:
    return str(c.get("kind") or "llm").lower() not in _NON_CHAT_KINDS


def detect(cfg: Optional[dict] = None) -> dict:
    """{"combos": [{name, models, source}], "models": [ids], "notes": [str]}

    Never raises: each source that fails adds a note instead, so the panel can
    say why a list is short."""
    import httpx
    cfg = {**load_config(), **(cfg or {})}
    base = normalise_url(cfg.get("base_url", ""))
    combos: dict = {}
    models: set = set()
    notes: list = []

    # 1. /v1/models (API key)
    try:
        r = httpx.get(f"{base}/models", headers=_headers(cfg), timeout=10)
        r.raise_for_status()
        for m in r.json().get("data") or []:
            mid = str(m.get("id") or "")
            if not mid:
                continue
            if m.get("owned_by") == "combo":
                if _chat_combo(m):
                    combos.setdefault(mid, {"models": [], "source": "api"})
            else:
                models.add(mid)
    except httpx.HTTPStatusError as e:
        notes.append(f"/v1/models: HTTP {e.response.status_code}"
                     + (" (API key recusada)" if e.response.status_code in (401, 403) else ""))
    except Exception as e:
        notes.append(f"/v1/models: {type(e).__name__}")

    # 2. dashboard API
    try:
        r = httpx.get(f"{_root_url(cfg.get('base_url', ''))}/api/combos",
                      headers=_headers(cfg), timeout=5)
        if r.status_code < 400:
            for c in (r.json() or {}).get("combos") or []:
                if isinstance(c, dict) and c.get("name") and _chat_combo(c):
                    e = combos.setdefault(str(c["name"]), {"models": [], "source": "dashboard"})
                    e["models"] = [str(x) for x in (c.get("models") or []) if isinstance(x, str)]
    except Exception:
        pass

    # 3. local db.json
    db = _read_local_db()
    for c in db.get("combos") or []:
        if isinstance(c, dict) and c.get("name") and _chat_combo(c):
            e = combos.setdefault(str(c["name"]), {"models": [], "source": "local"})
            if not e["models"]:
                e["models"] = [str(x) for x in (c.get("models") or []) if isinstance(x, str)]

    models -= set(combos)
    known_combos.clear()
    known_combos.update(combos)
    out = {"combos": [{"name": n, **v} for n, v in sorted(combos.items())],
           "models": sorted(models), "notes": notes}
    _emit("info", text=f"detect: {len(combos)} combo(s), {len(models)} modelo(s)"
                       + (f" · {'; '.join(notes)}" if notes else ""))
    return out


def is_combo(name: str) -> bool:
    return bool(name) and name in known_combos


def ping(cfg: Optional[dict] = None) -> bool:
    """Cheap liveness check for the status bar. Never raises."""
    import httpx
    cfg = cfg or load_config()
    root = _root_url(cfg.get("base_url", ""))
    ok = False
    for url in (f"{root}/api/health", f"{normalise_url(cfg.get('base_url', ''))}/models"):
        try:
            r = httpx.get(url, headers=_headers(cfg), timeout=3)
            if r.status_code < 500:
                ok = True
                break
        except Exception:
            continue
    stats["online"] = ok
    return ok


def test(cfg: Optional[dict] = None) -> tuple[bool, str]:
    """One sentence a person can act on."""
    import httpx
    cfg = {**load_config(), **(cfg or {})}
    base = normalise_url(cfg.get("base_url", ""))
    t0 = time.monotonic()
    try:
        models = list_models(cfg)
    except httpx.ConnectError:
        return False, f"Nada respondeu em {base} — o 9Router está rodando? (npx 9router)"
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code in (401, 403):
            return False, "O 9Router recusou a API key — confira em Dashboard → API Keys."
        return False, f"HTTP {code} em {base}/models"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    ms = int((time.monotonic() - t0) * 1000)
    model = str(cfg.get("model") or "").strip()
    try:
        found = detect(cfg)
        names = set(found["models"]) | {c["name"] for c in found["combos"]}
        n_c = len(found["combos"])
    except Exception:
        names, n_c = set(models), 0
    summary = f"{n_c} combo(s) + {len(names) - n_c} modelo(s)"
    if not model:
        return True, f"Conectado em {ms} ms — {summary}. Escolha um combo ou modelo."
    if names and model not in names:
        return False, (f"Conectado, mas '{model}' não existe aí. "
                       f"Use DETECTAR para ver os {summary}.")
    kind = "combo" if is_combo(model) else "modelo"
    return True, f"Conectado em {ms} ms · {kind} '{model}' OK · {summary}."
