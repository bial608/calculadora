@echo off
chcp 65001 >nul
setlocal
title ATLAS - desfazer update
cd /d "%~dp0"
echo.
echo   Volta o ATLAS para como estava antes do ultimo update.
echo   Feche o ATLAS antes de continuar.
echo.
pause
set "PY="
for %%V in (3.12 3.11 3.13) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
)
if not defined PY set "PY=python"
%PY% aplicar_update.py --desfazer %*
pause
endlocal
