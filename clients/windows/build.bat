@echo off
:: =============================================================================
:: Build Dyno-IP Windows Service .exe
:: Requires: Python 3.7+, pywin32, pyinstaller
:: Output: dist\dynoip-service.exe
:: =============================================================================

echo.
echo  Building Dyno-IP Windows Service...
echo  =====================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python not found in PATH
    exit /b 1
)

:: Install build dependencies
echo [1/3] Installing build dependencies...
pip install pywin32 pyinstaller --quiet

:: Copy dynoip_core.py to this directory for PyInstaller
echo [2/3] Preparing source...
copy /Y "%~dp0..\dynoip_core.py" "%~dp0dynoip_core.py" >nul

:: Build
echo [3/3] Building .exe...
cd /d "%~dp0"
pyinstaller --onefile --name dynoip-service --hidden-import win32timezone --hidden-import dynoip_core dynoip_win_service.py

:: Cleanup
del /f "%~dp0dynoip_core.py" >nul 2>&1

echo.
if exist "dist\dynoip-service.exe" (
    echo  ====================================
    echo   Build successful!
    echo  ====================================
    echo.
    echo  Output: %~dp0dist\dynoip-service.exe
    echo.
    echo  To install:
    echo    1. Copy dist\dynoip-service.exe to a permanent location
    echo    2. Copy install.bat alongside it
    echo    3. Run install.bat as Administrator
    echo.
) else (
    echo  [ERROR] Build failed. Check output above for errors.
)

pause
