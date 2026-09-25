@echo off
title CyberSec Dashboard Setup
echo ==========================================
echo  CyberSec Dashboard Installer
echo ==========================================
echo.
echo Launching automated setup script...
echo This will check for Python, MongoDB, and install all dependencies.
echo.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0setup\setup.ps1"

if exist "%~dp0.setup_success" (
    del "%~dp0.setup_success"
    rmdir /S /Q "%~dp0setup"
    echo.
    echo Setup completed successfully! All temporary setup files were cleaned up.
    echo Press any key to close this window...
    pause >nul
    (goto) 2>nul & del "%~f0"
) else (
    echo.
    echo Setup encountered an issue or validation failed. Keeping setup files for debugging.
    echo Press any key to close this window...
    pause >nul
)
