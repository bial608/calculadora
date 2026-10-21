@echo off
chcp 65001 >nul
setlocal
title ATLAS - fazer update
cd /d "%~dp0"

echo.
echo   ======================================================
echo     A.T.L.A.S  ^|  UPDATE
echo   ======================================================
echo.
echo   Feche o ATLAS antes de continuar.
echo   Suas API keys, configuracoes e memoria NAO serao alteradas.
echo.
pause

set "PY="
for %%V in (3.12 3.11 3.13) do (
    if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
    echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
    pause
    exit /b 1
)

%PY% "%~dp0_sistema\aplicar_update.py" %*
if errorlevel 1 (
    echo.
    echo [ERRO] O update nao foi aplicado. Nada foi alterado.
    pause
    exit /b 1
)
echo.
echo Pronto. Abra o ATLAS normalmente pelo INICIAR_ATLAS.bat.
pause
endlocal
