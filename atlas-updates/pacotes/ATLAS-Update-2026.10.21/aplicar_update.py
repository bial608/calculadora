"""
Aplica (ou desfaz) um update do ATLAS sem mexer no que você já configurou.

    python aplicar_update.py                 aplica, achando a pasta do ATLAS sozinho
    python aplicar_update.py --alvo "C:\\...\\ATLAS-9Router"
    python aplicar_update.py --desfazer      volta o último update aplicado

O QUE NUNCA É TOCADO
    config/api_keys.json (Gemini, 9Router, plugins, nome, cores), .env,
    os dados em memory/ (o que o ATLAS lembra de você), config/certs/, config/whatsapp_web/,
    .venv/ e qualquer arquivo que não esteja na lista do update.

SEGURANÇA
    Antes de trocar qualquer coisa, os arquivos atuais são copiados para
    <ATLAS>/_update_backups/<data-hora>/. Cada arquivo copiado é conferido por
    SHA-256. Se algo falhar no meio, tudo é revertido automaticamente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAYLOAD = HERE / "update"
MANIFEST = PAYLOAD / "manifest.json"

# Paths (relative, forward slashes) that an update may NEVER write or delete.
PROTECTED_PREFIXES = (
    "config/api_keys.json", ".env", "config/certs/",
    "config/whatsapp_web/", ".venv/", "venv/", "_update_backups/",
)
# memory/ holds both your data (long_term.json, *.db) and app code (*.py):
# only the data is off-limits.

G, Y, R, D, X = "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[0m"
if os.name == "nt":
    os.system("")


def say(color, msg):
    print(f"{color}{msg}{X}")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_protected(rel: str) -> bool:
    rel = rel.replace("\\", "/").lstrip("/")
    if rel.startswith("memory/") and not rel.endswith(".py"):
        return True
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in PROTECTED_PREFIXES)


def safe_rel(rel: str) -> bool:
    """No absolute paths, no '..' — an update can only write inside the install."""
    p = Path(rel)
    return not p.is_absolute() and ".." not in p.parts and ":" not in rel


# ─────────────────────────────────────────────────────────────────────────────
#  Finding the install
# ─────────────────────────────────────────────────────────────────────────────
def is_atlas(folder: Path) -> bool:
    try:
        main = (folder / "main.py").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return "AtlasLive" in main and (folder / "core" / "ninerouter.py").exists()


def candidates() -> list[Path]:
    seen, out = set(), []

    def add(p: Path):
        try:
            p = p.resolve()
        except Exception:
            return
        if p in seen:
            return
        seen.add(p)
        if is_atlas(p):
            out.append(p)

    # the update folder was extracted next to the install (siblings of it and
    # of its parent only — never wider, so an unrelated copy is not picked up)
    for up in list(HERE.parents)[:2]:
        add(up)
        try:
            for child in up.iterdir():
                if child.is_dir() and child != HERE:
                    add(child)
        except Exception:
            pass
    # usual places, two levels deep
    home = Path.home()
    roots = [home / n for n in ("Desktop", "Área de Trabalho", "Downloads", "Documents",
                                "Documentos", "OneDrive/Desktop", "OneDrive/Área de Trabalho",
                                "OneDrive/Documents", "OneDrive/Documentos")] + [home]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for a in root.iterdir():
                if not a.is_dir() or a.name.startswith("."):
                    continue
                add(a)
                try:
                    for b in a.iterdir():
                        if b.is_dir() and not b.name.startswith("."):
                            add(b)
                except Exception:
                    pass
        except Exception:
            pass
    out.sort(key=lambda p: (p / "main.py").stat().st_mtime, reverse=True)
    return out


def ask_folder() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        d = filedialog.askdirectory(title="Escolha a pasta do ATLAS (onde está o main.py)")
        root.destroy()
        if d:
            return Path(d)
    except Exception:
        pass
    try:
        d = input("Cole o caminho da pasta do ATLAS (onde está o main.py): ").strip().strip('"')
        return Path(d) if d else None
    except EOFError:
        return None


def confirm(p: Path, assume_yes: bool) -> Path | None:
    if assume_yes:
        return p
    try:
        ans = input(f"Atualizar esta pasta?  {p}\n[S/n]: ").strip().lower()
    except EOFError:
        return None
    return p if ans in ("", "s", "sim", "y", "yes") else None


def find_install(explicit: str | None, assume_yes: bool) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        return p if is_atlas(p) else None
    # Strongest signal: the update folder sits INSIDE an install.
    for up in HERE.parents:
        if is_atlas(up):
            return confirm(up, assume_yes)
    found = candidates()
    if len(found) == 1:
        return confirm(found[0], assume_yes)
    if found and assume_yes:
        say(R, "Há mais de uma instalação do ATLAS; diga qual com --alvo \"<pasta>\".")
        for p in found:
            print(f"  {p}")
        return None
    if found:
        say(Y, "Encontrei mais de uma instalação do ATLAS:")
        for i, p in enumerate(found, 1):
            print(f"  {i}. {p}")
        try:
            pick = input("Número da que deve ser atualizada (Enter = cancelar): ").strip()
            return found[int(pick) - 1] if pick else None
        except Exception:
            return None
    say(Y, "Não achei a pasta do ATLAS automaticamente.")
    p = ask_folder()
    return confirm(p, assume_yes) if p and is_atlas(p) else None


# ─────────────────────────────────────────────────────────────────────────────
#  Apply / undo
# ─────────────────────────────────────────────────────────────────────────────
def apply(target: Path) -> bool:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = man.get("files") or []
    deletes = man.get("delete") or []
    say(G, f"\n▶ Update {man.get('version')} → {target}")
    print(f"  {man.get('title', '')}")

    for item in files:
        if not safe_rel(item["path"]) or is_protected(item["path"]):
            say(R, f"✖ update inválido: tenta escrever em {item['path']} — abortado")
            return False
        src = PAYLOAD / "files" / item["path"]
        if not src.exists() or sha256(src) != item["sha256"]:
            say(R, f"✖ arquivo do update corrompido: {item['path']} — baixe o update de novo")
            return False

    todo = [i for i in files
            if not (target / i["path"]).exists() or sha256(target / i["path"]) != i["sha256"]]
    todo_del = [r for r in deletes if safe_rel(r) and not is_protected(r) and (target / r).exists()]
    if not todo and not todo_del:
        say(G, "\n✔ Esta instalação já está com este update. Nada foi alterado.")
        return True

    # A backup folder is never reused: re-running in the same second must not
    # overwrite the copy of the ORIGINAL files with already-updated ones.
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    bdir = target / "_update_backups" / stamp
    n = 2
    while bdir.exists():
        bdir = target / "_update_backups" / f"{stamp}_{n}"
        n += 1
    bdir.mkdir(parents=True)
    record = {"version": man.get("version"), "applied_at": stamp,
              "replaced": [], "created": [], "deleted": []}

    done: list[tuple[str, str]] = []           # for automatic rollback
    try:
        for item in files:
            rel = item["path"]
            dst = target / rel
            if item not in todo:
                print(f"  {D}= {rel} (já atualizado){X}")
                continue
            if dst.exists():
                (bdir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, bdir / rel)
                record["replaced"].append(rel)
                kind = "~"
            else:
                record["created"].append(rel)
                kind = "+"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PAYLOAD / "files" / rel, dst)
            if sha256(dst) != item["sha256"]:
                raise RuntimeError(f"cópia não confere: {rel}")
            done.append((kind, rel))
            print(f"  {G if kind == '+' else Y}{kind} {rel}{X}")
        for rel in deletes:
            if not safe_rel(rel) or is_protected(rel):
                continue
            p = target / rel
            if p.exists():
                (bdir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(bdir / rel))
                record["deleted"].append(rel)
                print(f"  {R}- {rel} (guardado no backup){X}")
        # every updated Python file must at least compile
        for _, rel in done:
            if rel.endswith(".py"):
                py_compile.compile(str(target / rel), doraise=True)
    except Exception as e:
        say(R, f"\n✖ Falhou: {e}\n  Revertendo…")
        (bdir / "backup.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        undo(target, bdir)
        return False

    (bdir / "backup.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    (target / "VERSION_ATLAS.json").write_text(json.dumps(
        {"version": man.get("version"), "title": man.get("title"), "applied_at": stamp,
         "files": [i["path"] for i in files]}, indent=2, ensure_ascii=False), encoding="utf-8")
    say(G, f"\n✔ Update aplicado: {len(record['created'])} novo(s), "
           f"{len(record['replaced'])} atualizado(s).")
    print(f"  Suas configurações e API keys não foram tocadas.")
    print(f"  Backup: {bdir}")
    if any(i["path"] == "requirements.txt" for i in files):
        say(Y, "  requirements.txt mudou: o INICIAR_ATLAS.bat vai instalar o que faltar na próxima vez.")
    return True


def latest_backup(target: Path) -> Path | None:
    root = target / "_update_backups"
    if not root.is_dir():
        return None
    bs = sorted((d for d in root.iterdir() if (d / "backup.json").exists()), reverse=True)
    return bs[0] if bs else None


def undo(target: Path, bdir: Path | None = None) -> bool:
    bdir = bdir or latest_backup(target)
    if bdir is None:
        say(Y, "Nenhum update para desfazer.")
        return False
    rec = json.loads((bdir / "backup.json").read_text(encoding="utf-8"))
    for rel in rec.get("created", []):
        p = target / rel
        if p.exists() and safe_rel(rel) and not is_protected(rel):
            p.unlink()
            print(f"  {R}- {rel}{X}")
    for rel in rec.get("replaced", []) + rec.get("deleted", []):
        src = bdir / rel
        if src.exists() and safe_rel(rel) and not is_protected(rel):
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / rel)
            print(f"  {Y}↺ {rel}{X}")
    (bdir / "backup.json").rename(bdir / "backup.desfeito.json")
    ver = target / "VERSION_ATLAS.json"
    if ver.exists():
        ver.unlink()
    say(G, f"✔ Desfeito: voltou ao estado de antes do update {rec.get('version')}.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alvo", help="pasta do ATLAS")
    ap.add_argument("--desfazer", action="store_true")
    ap.add_argument("--sim", action="store_true", help="não perguntar")
    a = ap.parse_args()

    target = find_install(a.alvo, a.sim)
    if target is None:
        say(R, "✖ Nenhuma pasta do ATLAS escolhida (ela precisa ter o main.py do ATLAS). "
               "Nada foi alterado.")
        return 2
    say(D, f"ATLAS em: {target}")
    ok = undo(target) if a.desfazer else apply(target)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
