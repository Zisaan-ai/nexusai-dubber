@echo off
title NexusAI Dubber Studio — Windows Installer
color 0A
cd /d "%~dp0"

echo ================================================================
echo           ⚡ NexusAI Dubber Studio — Windows Installer ⚡
echo ================================================================
echo.
echo Installing desktop shortcuts and configuring application...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "installer\create_shortcuts.ps1"

echo.
pause
