@echo off
title NexusAI Dubber Studio — Windows Uninstaller
color 0C
cd /d "%~dp0"

echo ================================================================
echo           ⚡ NexusAI Dubber Studio — Uninstaller ⚡
echo ================================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "installer\uninstall_shortcuts.ps1"
echo.
pause
