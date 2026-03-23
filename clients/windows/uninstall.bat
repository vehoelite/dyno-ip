@echo off
:: Dyno-IP DDNS Client — Windows Uninstaller (Run as Administrator)

echo.
echo  Dyno-IP Dynamic DNS — Uninstaller
echo  ===================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Run as Administrator.
    pause
    exit /b 1
)

set "EXE=%~dp0dynoip-service.exe"

echo [1/3] Stopping service...
net stop DynoIPUpdate >nul 2>&1

echo [2/3] Removing service...
if exist "%EXE%" (
    "%EXE%" remove
) else (
    sc delete DynoIPUpdate >nul 2>&1
)

echo [3/3] Done.
echo.
echo  Config and logs preserved in: %PROGRAMDATA%\DynoIP
echo  Delete manually if no longer needed.
echo.

pause
