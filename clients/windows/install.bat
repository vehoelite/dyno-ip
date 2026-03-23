@echo off
:: =============================================================================
:: Dyno-IP DDNS Client — Windows Installer
:: Run as Administrator!
:: =============================================================================

echo.
echo  ====================================
echo   Dyno-IP Dynamic DNS  -  Installer
echo  ====================================
echo.

:: Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This installer must be run as Administrator.
    echo         Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Locate the exe
set "EXE=%~dp0dynoip-service.exe"
if not exist "%EXE%" (
    echo [ERROR] dynoip-service.exe not found in %~dp0
    echo         Build it first: pyinstaller --onefile --name dynoip-service dynoip_win_service.py
    pause
    exit /b 1
)

:: Create config directory
set "CONFIGDIR=%PROGRAMDATA%\DynoIP"
if not exist "%CONFIGDIR%" mkdir "%CONFIGDIR%"

:: Install the service
echo [1/4] Installing service...
"%EXE%" install
if %errorLevel% neq 0 (
    echo [ERROR] Service installation failed.
    pause
    exit /b 1
)

:: Set service to auto-start
echo [2/4] Setting auto-start...
sc config DynoIPUpdate start= auto >nul 2>&1

:: Set recovery: restart on failure
echo [3/4] Configuring recovery (restart on failure)...
sc failure DynoIPUpdate reset= 86400 actions= restart/5000/restart/10000/restart/30000 >nul 2>&1

:: Open config for editing
echo [4/4] Opening configuration...
if not exist "%CONFIGDIR%\config.ini" (
    "%EXE%" --configure
) else (
    echo Config already exists at: %CONFIGDIR%\config.ini
)

echo.
echo  ====================================
echo   Installation Complete!
echo  ====================================
echo.
echo  IMPORTANT: Edit your token in:
echo    %CONFIGDIR%\config.ini
echo.
echo  Then start the service:
echo    net start DynoIPUpdate
echo.
echo  Or start from Services (services.msc)
echo.
echo  Logs: %CONFIGDIR%\dynoip.log
echo.

pause
