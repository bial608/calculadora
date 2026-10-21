"""
ensinar_tarefa — "vamos fazer juntos": you guide ATLAS through a task it could
not do alone, one spoken step at a time, and it saves the result as a skill.

The real work lives in actions/task_agent.py (next to the autonomous agent and
the skill store it shares). This file only exposes the tool so Gemini can route
to it; action_loader allows one TOOL per file.
"""
from __future__ import annotations

from actions.task_agent import ensinar_tarefa

TOOL = {
    "name": "ensinar_tarefa",
    "description": (
        "Teaching mode — use when the user wants to show you how to do something, "
        "or after executar_tarefa failed and the user agrees to do it together. "
        "The user guides you ONE step at a time by voice; you perform each step "
        "and remember it, then save it as a skill so next time executar_tarefa "
        "does it alone. Call action='start' with the goal when the user says "
        "things like 'deixa eu te ensinar', 'vamos fazer juntos', 'te mostro como "
        "faz'. For each thing the user then says to do, call action='step' with "
        "their words in 'instruction' (e.g. 'clica no campo de busca', 'escreve "
        "oi'). When the user says 'pronto'/'terminei'/'acabou', call "
        "action='finish' to save it. action='cancel' discards it. Do NOT use this "
        "to do a task yourself — that is executar_tarefa."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "start | step | finish | cancel"},
            "goal": {"type": "STRING", "description": "What you are learning to do (with action='start')."},
            "instruction": {"type": "STRING",
                            "description": "The user's words for THIS single step (with action='step')."},
        },
        "required": ["action"],
    },
    "handler": ensinar_tarefa,
    "tier": "core",
    "brief": "Learn a task the user guides you through step by step, and save it as a skill.",
}
