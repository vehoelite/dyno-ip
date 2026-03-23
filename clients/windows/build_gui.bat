@echo off
:: =============================================================================
:: Build Dyno-IP Desktop GUI .exe
:: Requires: Python 3.10+, customtkinter, requests, Pillow, pyinstaller
:: Output:   dist\DynoIP.exe
:: =============================================================================

echo.
echo  Building Dyno-IP Desktop GUI...
echo  ================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python not found in PATH
    exit /b 1
)

:: Install build dependencies
echo [1/3] Installing dependencies...
pip install customtkinter requests Pillow pystray pyinstaller --quiet --upgrade

:: Build
echo [2/3] Building .exe ...
cd /d "%~dp0"
pyinstaller --onefile --windowed --name DynoIP ^
    --hidden-import customtkinter ^
    --hidden-import pystray._win32 ^
    --collect-data customtkinter ^
    --icon=dynoip.ico ^
    dynoip_gui.py 2>nul || (
    pyinstaller --onefile --windowed --name DynoIP ^
        --hidden-import customtkinter ^
        --hidden-import pystray._win32 ^
        --collect-data customtkinter ^
        dynoip_gui.py
)

echo.
if exist "dist\DynoIP.exe" (
    echo  ================================
    echo   Build successful!
    echo  ================================
    echo.
    echo  Output: %~dp0dist\DynoIP.exe
    echo  Size:
    for %%F in (dist\DynoIP.exe) do echo   %%~zF bytes
    echo.
    echo  Run it: dist\DynoIP.exe
    echo.
) else (
    echo  [ERROR] Build failed. Check output above for errors.
)

echo [3/3] Cleanup...
rmdir /s /q build 2>nul
del /f DynoIP.spec 2>nul

pause
