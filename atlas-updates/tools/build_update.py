"""
Monta um pacote de update do ATLAS com SÓ o que mudou entre dois commits.

    python build_update.py <commit-base> <versão> "<título>" <pasta-saída>

O pacote:  fazer_update.bat · desfazer_update.bat · aplicar_update.py ·
           LEIA-ME-UPDATE.md · update/manifest.json · update/files/...
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent.parent
APP = "atlas-9router"


def git(*args) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True,
                          capture_output=True, text=True).stdout


def main():
    base, version, title, out = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
    sys.path.insert(0, str(TOOLS))
    from aplicar_update import is_protected

    changed, deleted = [], []
    for line in git("diff", "--name-status", "--no-renames", base, "HEAD", "--", APP).splitlines():
        st, path = line.split("\t", 1)
        rel = path[len(APP) + 1:]
        if "__pycache__" in rel or is_protected(rel):
            continue
        (deleted if st == "D" else changed).append(rel)

    if out.exists():
        shutil.rmtree(out)
    sysdir = out / "_sistema"          # machinery hidden here; root holds only .bat + README
    files = []
    for rel in sorted(changed):
        data = subprocess.run(["git", "-C", str(REPO), "show", f"HEAD:{APP}/{rel}"],
                              check=True, capture_output=True).stdout
        dst = sysdir / "update" / "files" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        files.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})

    manifest = {"version": version, "title": title, "base": base,
                "head": git("rev-parse", "--short", "HEAD").strip(),
                "files": files, "delete": sorted(deleted)}
    (sysdir / "update").mkdir(parents=True, exist_ok=True)
    (sysdir / "update" / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(TOOLS / "aplicar_update.py", sysdir / "aplicar_update.py")
    for name in ("fazer_update.bat", "desfazer_update.bat"):
        shutil.copy2(TOOLS / name, out / name)
    notes = TOOLS.parent / "notas" / f"{version}.md"
    if notes.exists():
        shutil.copy2(notes, out / "LEIA-ME-UPDATE.md")
    print(f"{len(files)} arquivo(s), {len(deleted)} removido(s) -> {out}")
    for f in files:
        print("  ", f["path"])


if __name__ == "__main__":
    main()
