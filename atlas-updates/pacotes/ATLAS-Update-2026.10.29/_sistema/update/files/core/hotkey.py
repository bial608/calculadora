"""
Push-to-talk — hold a key, speak, release.

Why this exists
---------------
Wake-word is hands-free but it is not always what you want: in a meeting, in a
noisy room, or when you simply do not feel like saying a name out loud, a key
you hold is faster and never mishears. It is also the natural way to use the
assistant while another window has focus.

How it works, and what it costs
-------------------------------
Zero new dependencies, best available mechanism per platform:

* **Windows** — `GetAsyncKeyState` polled from one small thread. This is
  deliberately *not* `RegisterHotKey`, which only reports a press: push-to-talk
  needs the release too, and it needs to work while another application has
  focus. Polling two virtual-key codes 30 times a second is a rounding error of
  CPU and needs no message loop.
* **macOS / Linux** — no portable way to read global key state without pulling
  in a new package or asking for accessibility permissions, so the chord is
  bound as an application shortcut instead: it works whenever the assistant's
  window has focus. `scope` reports which of the two you got, so the UI can say
  so honestly rather than pretending.

The class never raises. If the platform hook cannot be installed it simply
reports `scope == "window"` and the Qt shortcut carries it.
"""

from __future__ import annotations

import platform
import threading
import time
from typing import Callable

_OS = platform.system()

# The default chord. Ctrl+Space is free in most desktop environments and is the
# same finger shape on every keyboard layout, which matters for a worldwide app.
DEFAULT_CHORD = ("ctrl", "space")

# Windows virtual-key codes for the names we accept.
_VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12,
    "space": 0x20, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "capslock": 0x14, "insert": 0x2D,
    "k": 0x4B,
}

# Qt key sequence text for the same chord, used by the windowed fallback.
_QT_NAME = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "space": "Space",
            "f8": "F8", "f9": "F9", "f10": "F10",
            "capslock": "CapsLock", "insert": "Ins"}

_MODIFIERS = ("ctrl", "shift", "alt")

# Mute / unmute the microphone from anywhere.
MUTE_CHORD = ("ctrl", "shift", "alt", "space")

_POLL_HZ = 30.0
# A key has to be down this long before we call it speech. It stops a stray
# brush of the chord from opening the microphone.
_DEBOUNCE_S = 0.06


def chord_label(chord=DEFAULT_CHORD) -> str:
    """Human-readable name of the chord, for the UI and the logs."""
    return "+".join(_QT_NAME.get(k, k.title()) for k in chord)


def qt_sequence(chord=DEFAULT_CHORD) -> str:
    """The same chord as a QKeySequence string."""
    return "+".join(_QT_NAME.get(k, k.title()) for k in chord)


class PushToTalk:
    """Calls `on_change(held: bool)` whenever the chord is pressed or released.

    Start it once; it is safe to start and stop repeatedly, and safe to stop a
    detector that never started.
    """

    def __init__(self, on_change: Callable[[bool], None], chord=DEFAULT_CHORD):
        self._on_change = on_change
        self._chord = tuple(chord)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._held = False
        self._scope = "window"

    # ── state ───────────────────────────────────────────────────────────────

    @property
    def held(self) -> bool:
        return self._held

    @property
    def scope(self) -> str:
        """'global' once a system-wide hook is running, else 'window'."""
        return self._scope

    @property
    def label(self) -> str:
        return chord_label(self._chord)

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> str:
        """Begin watching. Returns the scope actually achieved."""
        self.stop()
        self._stop.clear()
        if _OS == "Windows" and self._can_poll():
            self._scope = "global"
            self._thread = threading.Thread(
                target=self._poll_loop, name="push-to-talk", daemon=True)
            self._thread.start()
        else:
            self._scope = "window"
        return self._scope

    def stop(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None and t.is_alive():
            t.join(timeout=1.0)
        self._set_held(False)

    # ── the windowed fallback drives this directly ──────────────────────────

    def set_held(self, held: bool) -> None:
        """Feed a press/release from a Qt shortcut (non-Windows, or no hook)."""
        self._set_held(bool(held))

    # ── internals ───────────────────────────────────────────────────────────

    def _can_poll(self) -> bool:
        try:
            import ctypes
            ctypes.windll.user32.GetAsyncKeyState  # noqa: B018 — presence check
            return all(k in _VK for k in self._chord)
        except Exception:
            return False

    def _set_held(self, held: bool) -> None:
        if held == self._held:
            return
        self._held = held
        try:
            self._on_change(held)
        except Exception:
            pass          # a listener fault must never kill the watcher

    def _poll_loop(self) -> None:
        import ctypes
        user32 = ctypes.windll.user32
        codes = [_VK[k] for k in self._chord]
        # Modifiers that are NOT part of the chord must be up. Without this,
        # Ctrl+Shift+Alt+Space (the mute toggle) also counts as Ctrl+Space and
        # opens the microphone for push-to-talk at the same time.
        extra = [_VK[m] for m in _MODIFIERS if m not in self._chord]
        period = 1.0 / _POLL_HZ
        down_since = 0.0

        while not self._stop.is_set():
            try:
                # The high bit of the return value is "currently down".
                down = (all(user32.GetAsyncKeyState(c) & 0x8000 for c in codes)
                        and not any(user32.GetAsyncKeyState(c) & 0x8000 for c in extra))
            except Exception:
                break     # driver or session teardown — fall back to windowed
            now = time.monotonic()
            if down:
                if down_since == 0.0:
                    down_since = now
                elif now - down_since >= _DEBOUNCE_S:
                    self._set_held(True)
            else:
                down_since = 0.0
                self._set_held(False)
            self._stop.wait(period)

        self._set_held(False)
        self._scope = "window"


class GlobalToggle:
    """Calls `on_press()` ONCE each time the chord goes down — a toggle, not a
    hold. Global on Windows (same polling as push-to-talk, no new package);
    elsewhere `scope` is "window" and a Qt shortcut does the job instead.
    Holding the keys does not repeat: the chord must be released first.
    """

    def __init__(self, on_press: Callable[[], None], chord=MUTE_CHORD):
        self._on_press = on_press
        self._chord = tuple(chord)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._scope = "window"

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def label(self) -> str:
        return chord_label(self._chord)

    def start(self) -> str:
        self.stop()
        self._stop.clear()
        try:
            if _OS == "Windows" and all(k in _VK for k in self._chord):
                import ctypes
                ctypes.windll.user32.GetAsyncKeyState  # noqa: B018
                self._scope = "global"
                self._thread = threading.Thread(target=self._loop, daemon=True,
                                                name="mute-toggle")
                self._thread.start()
                return self._scope
        except Exception:
            pass
        self._scope = "window"
        return self._scope

    def stop(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None and t.is_alive():
            t.join(timeout=1.0)

    def _loop(self) -> None:
        import ctypes
        user32 = ctypes.windll.user32
        codes = [_VK[k] for k in self._chord]
        armed, down_since = True, 0.0
        while not self._stop.is_set():
            try:
                down = all(user32.GetAsyncKeyState(c) & 0x8000 for c in codes)
            except Exception:
                break
            now = time.monotonic()
            if down:
                if down_since == 0.0:
                    down_since = now
                elif armed and now - down_since >= _DEBOUNCE_S:
                    armed = False
                    try:
                        self._on_press()
                    except Exception:
                        pass
            else:
                down_since, armed = 0.0, True
            self._stop.wait(1.0 / _POLL_HZ)
        self._scope = "window"
