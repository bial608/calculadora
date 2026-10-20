#!/usr/bin/env bash
# JARVIS — MARK LVI + 9Router (macOS / Linux)
set -e
cd "$(dirname "$0")"

PY=""
for v in python3.12 python3.11 python3.13 python3; do
  if command -v "$v" >/dev/null 2>&1 && "$v" -c 'import sys; sys.exit(0 if (3,11)<=sys.version_info[:2]<=(3,13) else 1)'; then
    PY="$v"; break
  fi
done
[ -z "$PY" ] && { echo "[ERRO] Python 3.11–3.13 não encontrado."; exit 1; }
echo "[ok] Python: $PY"

[ -x .venv/bin/python ] || "$PY" -m venv .venv
VPY=.venv/bin/python
if ! cmp -s requirements.txt .venv/.installed; then
  echo "[..] Instalando dependências…"
  "$VPY" -m pip install --upgrade pip >/dev/null
  "$VPY" -m pip install -r requirements.txt
  "$VPY" -m playwright install chromium >/dev/null 2>&1 || true
  cp requirements.txt .venv/.installed
fi

if [ ! -f config/api_keys.json ] || [ "$1" = "--config" ]; then
  "$VPY" configurar.py
fi

echo "[>>] Iniciando JARVIS… (F12 = Dev Console, Ctrl+9 = 9Router)"
exec "$VPY" main.py
