"""
capabilities — how ATLAS stays fast with many features.

THE IDEA YOU ASKED FOR: "ele sabe que as features existem e só chama quando
precisa." That is exactly how this works, and it is cheap because of ONE rule:

    A feature's MODULE is tiny to import; its HEAVY parts load on first use.

Importing `actions/*.py` at boot only has to read a declaration (name +
description) — stdlib only. The expensive things (opencv, playwright, mss,
pyautogui, whisper, a 300 MB model) are imported INSIDE the handler, the first
time the feature actually runs. So the model is told every capability exists
(one short line each), the prompt stays small, boot stays instant, and nothing
heavy is paid for until the moment a capability is used — and never at all for
the ones you don't use this session.

This module provides:
  * `lazy(import_path)` — a tiny helper to defer a heavy import to call time.
  * `HEAVY` — the packages that must never be imported at module top level.
  * `scan_heavy_top_imports(dir)` — audit used by the test suite to keep it so.

Gated features (turned off in the Recursos panel) are not even offered to the
model, so they cost zero prompt and zero code. That is the second half of the
speed story and lives in main.py / the registries.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

# Packages that pull in big native deps or models. Importing any of these at the
# top of an action module would slow every launch, whether or not the feature is
# used — so they belong inside the function that needs them.
HEAVY = {
    "cv2", "opencv-python", "mss", "pyautogui", "pyperclip",
    "playwright", "PIL", "pillow", "faster_whisper", "whisper", "piper",
    "openwakeword", "pvporcupine", "torch", "onnxruntime", "mediapipe",
    "pandas", "pydub", "pdfplumber", "PyPDF2", "docx", "pptx", "openpyxl",
    "google", "httpx",
}


def lazy(import_path: str):
    """Import 'pkg.mod:attr' (or 'pkg.mod') only when first called.

        screenshot = lazy("mss:mss")
        ...inside the handler: shot = screenshot()
    """
    mod, _, attr = import_path.partition(":")
    cache = {}

    def _get():
        if "v" not in cache:
            m = importlib.import_module(mod)
            cache["v"] = getattr(m, attr) if attr else m
        return cache["v"]

    def _call(*a, **k):
        return _get()(*a, **k)
    _call.get = _get
    return _call


def _top_level_imports(path: Path) -> set[str]:
    """Top-level (module-scope) import names in a .py file — NOT those inside
    functions, which are the deferred ones we want."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return set()
    names: set[str] = set()
    for node in tree.body:            # body only = module scope
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def scan_heavy_top_imports(actions_dir: Path) -> dict[str, set[str]]:
    """{filename: {heavy packages imported at module top}} — empty means every
    action is boot-cheap. Used by the tests to prevent a regression that would
    slow startup as features are added."""
    out = {}
    for p in sorted(Path(actions_dir).glob("*.py")):
        if p.name.startswith("_"):
            continue
        bad = _top_level_imports(p) & HEAVY
        if bad:
            out[p.name] = bad
    return out
