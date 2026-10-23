@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" configurar.py
) else (
    py -3 configurar.py || python configurar.py
)
pause
