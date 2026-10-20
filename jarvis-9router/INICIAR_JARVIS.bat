@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title JARVIS - MARK LVI + 9Router
cd /d "%~dp0"

echo.
echo   ======================================================
echo     J.A.R.V.I.S  ^|  MARK LVI  ^|  ears=Gemini  brain=9Router
echo   ======================================================
echo.

REM -- 1. Achar um Python suportado (3.11 - 3.13) -----------------------------
set "PY="
for %%V in (3.12 3.11 3.13) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if (3,11)<=sys.version_info[:2]<=(3,13) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERRO] Python 3.11, 3.12 ou 3.13 nao encontrado.
    echo        Baixe em https://www.python.org/downloads/ ^(marque "Add to PATH"^).
    pause
    exit /b 1
)
echo [ok] Python: %PY%

REM -- 2. Ambiente virtual ----------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] Criando ambiente virtual .venv ...
    %PY% -m venv .venv || (echo [ERRO] falha ao criar venv & pause & exit /b 1)
)
set "VPY=.venv\Scripts\python.exe"

REM -- 3. Dependencias (so na primeira vez, ou se requirements mudar) ---------
set "STAMP=.venv\.installed"
set "NEED=1"
if exist "%STAMP%" (
    fc /b requirements.txt "%STAMP%" >nul 2>&1 && set "NEED=0"
)
if "%NEED%"=="1" (
    echo [..] Instalando dependencias ^(primeira vez demora alguns minutos^)...
    "%VPY%" -m pip install --upgrade pip >nul
    "%VPY%" -m pip install -r requirements.txt || (echo [ERRO] pip falhou & pause & exit /b 1)
    "%VPY%" -m playwright install chromium >nul 2>&1
    copy /y requirements.txt "%STAMP%" >nul
    echo [ok] Dependencias instaladas.
) else (
    echo [ok] Dependencias ja instaladas.
)

REM -- 4. Configuracao (Gemini + 9Router) -------------------------------------
if not exist "config\api_keys.json" (
    echo.
    echo [..] Primeira execucao: vamos configurar as chaves.
    "%VPY%" configurar.py
)
if /i "%~1"=="--config" "%VPY%" configurar.py

REM -- 5. Ligar ---------------------------------------------------------------
echo.
echo [^>^>] Iniciando JARVIS...  (F12 = Dev Console, Ctrl+9 = 9Router)
"%VPY%" main.py
if errorlevel 1 (
    echo.
    echo [ERRO] JARVIS encerrou com erro. Veja as mensagens acima.
    pause
)
endlocal
